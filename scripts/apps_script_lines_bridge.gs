/**
 * Aurora Tigers U13A — 100% Free SMS-to-Email Lineup Bridge (Google Apps Script)
 * -----------------------------------------------------------------------------
 * Uses your EXISTING Gmail account (with "+lines" alias, e.g. yourname+lines@gmail.com)
 * so you don't need to create a new email or pay for Twilio.
 *
 * Setup: https://script.google.com -> New Project -> Paste this file.
 * Add a Time-driven trigger for `syncTextedLinesToFirestore` every 5 minutes.
 */

const CONFIG = {
  // Use your existing Gmail with "+lines" (e.g. "to:scott+lines@gmail.com")
  GMAIL_SEARCH_QUERY: 'is:unread (to:+lines OR subject:"Tigers Lines" OR subject:"Game Lines")',
  FIREBASE_PROJECT_ID: 'aurora-tigers-u13a',
  GAMES_LIBRARY_RAW_URL: 'https://raw.githubusercontent.com/ScottRepository/U13A-Tigers-2026-2027/main/games_library.json',
  GAMESHEET_RAW_URL: 'https://raw.githubusercontent.com/ScottRepository/U13A-Tigers-2026-2027/main/gamesheet_league_data.json',
  // Optional: Coach's carrier SMS gateway email for pre-game reminders ($0 free)
  // Rogers: @pcs.rogers.com | Bell: @txt.bell.ca | Telus: @msg.telus.com | Fido: @fido.ca | Koodo: @msg.koodomobile.com
  COACH_SMS_EMAIL: '',
  // Optional: Reply-To alias so coach's SMS reply routes straight back to +lines
  REPLY_TO_ALIAS: ''
};

const ROSTER = {
  '3': 'Mason', '4': 'Kaleb', '7': 'Hunter', '8': 'Chase', '9': 'Brayden',
  '11': 'Nathan', '13': 'Matthew', '14': 'Owen', '15': 'Jackson', '18': 'Nathan',
  '19': 'Cole', '21': 'Landon', '23': 'Easton', '27': 'Lucas', '28': 'Liam',
  '44': 'Colton', '88': 'Noah', '98': 'Hudson'
};

function syncTextedLinesToFirestore() {
  const threads = GmailApp.search(CONFIG.GMAIL_SEARCH_QUERY, 0, 10);
  if (!threads.length) return;

  const targetGame = getTargetGameInfo();
  if (!targetGame || !targetGame.id) {
    Logger.log('No target game found.');
    return;
  }

  threads.forEach(thread => {
    const messages = thread.getMessages();
    const latestMsg = messages[messages.length - 1];
    const body = latestMsg.getPlainBody() || '';
    const parsed = parseLinesText(body);

    if (parsed.matchedAny) {
      writeLineupToFirestore(targetGame.id, targetGame.title, parsed.lineup, parsed.dressed);
      Logger.log('Saved texted lines for ' + targetGame.id + ': ' + JSON.stringify(parsed.lineup));
      thread.markRead();
    }
  });
}

function sendPreGameLineupReminder() {
  if (!CONFIG.COACH_SMS_EMAIL) {
    Logger.log('Set CONFIG.COACH_SMS_EMAIL first (e.g. 9055551234@txt.bell.ca).');
    return;
  }
  const nextGame = getNextScheduledGameInfo();
  if (!nextGame) return;

  const subject = 'Tigers Lines: ' + nextGame.opponent;
  const body =
    'Game today vs ' + nextGame.opponent + ' (' + nextGame.time + ').\n' +
    'Reply with lines to auto-load video AI:\n' +
    'L1: # # #\nL2: # # #\nL3: # # #\nD1: # #\nD2: # #\nG: #';

  const opts = CONFIG.REPLY_TO_ALIAS ? { replyTo: CONFIG.REPLY_TO_ALIAS } : {};
  GmailApp.sendEmail(CONFIG.COACH_SMS_EMAIL, subject, body, opts);
}

function parseLinesText(rawText) {
  const lineup = {
    f1: { lw: '', c: '', rw: '' },
    f2: { lw: '', c: '', rw: '' },
    f3: { lw: '', c: '', rw: '' },
    d1: { ld: '', rd: '' },
    d2: { ld: '', rd: '' },
    d3: { ld: '', rd: '' },
    goalie: '13'
  };
  const dressed = new Set();
  let matchedAny = false;

  const resolveTokens = (txt) => {
    const out = [];
    const tokens = txt.replace(/[#,:;/\-]+/g, ' ').trim().split(/\s+/);
    tokens.forEach(tok => {
      if (!tok) return;
      if (ROSTER[tok]) { out.push(tok); return; }
      const lower = tok.toLowerCase();
      for (const [num, name] of Object.entries(ROSTER)) {
        if (lower.length >= 3 && name.toLowerCase().startsWith(lower)) {
          out.push(num);
          break;
        }
      }
    });
    return out;
  };

  rawText.split(/[\r\n|]+/).forEach(line => {
    const clean = line.trim();
    if (!clean) return;
    const lower = clean.toLowerCase();
    const stripped = clean.replace(/^(line\s*\d|l\d|pair\s*\d|d\d|goalie|g)\b/i, '');
    const ids = resolveTokens(stripped);
    ids.forEach(id => dressed.add(Number(id)));

    if (/^(l1|line\s*1)\b/.test(lower) && ids.length) {
      lineup.f1 = { lw: ids[0] || '', c: ids[1] || '', rw: ids[2] || '' }; matchedAny = true;
    } else if (/^(l2|line\s*2)\b/.test(lower) && ids.length) {
      lineup.f2 = { lw: ids[0] || '', c: ids[1] || '', rw: ids[2] || '' }; matchedAny = true;
    } else if (/^(l3|line\s*3)\b/.test(lower) && ids.length) {
      lineup.f3 = { lw: ids[0] || '', c: ids[1] || '', rw: ids[2] || '' }; matchedAny = true;
    } else if (/^(d1|pair\s*1)\b/.test(lower) && ids.length) {
      lineup.d1 = { ld: ids[0] || '', rd: ids[1] || '' }; matchedAny = true;
    } else if (/^(d2|pair\s*2)\b/.test(lower) && ids.length) {
      lineup.d2 = { ld: ids[0] || '', rd: ids[1] || '' }; matchedAny = true;
    } else if (/^(d3|pair\s*3)\b/.test(lower) && ids.length) {
      lineup.d3 = { ld: ids[0] || '', rd: ids[1] || '' }; matchedAny = true;
    } else if (/^(g|goalie)\b/.test(lower) && ids.length) {
      lineup.goalie = ids[0]; matchedAny = true;
    }
  });

  return { matchedAny, lineup, dressed: Array.from(dressed) };
}

function getTargetGameInfo() {
  try {
    const resp = UrlFetchApp.fetch(CONFIG.GAMES_LIBRARY_RAW_URL);
    const data = JSON.parse(resp.getContentText());
    const games = data.games || [];
    const pending = games.find(g => String(g.ai_engine || '').includes('Pending'));
    const target = pending || games[0];
    return target ? { id: target.id, title: target.title } : null;
  } catch (e) {
    return null;
  }
}

function getNextScheduledGameInfo() {
  try {
    const resp = UrlFetchApp.fetch(CONFIG.GAMESHEET_RAW_URL);
    const data = JSON.parse(resp.getContentText());
    const upcoming = (data.upcoming_games || [])[0];
    if (!upcoming) return null;
    return {
      opponent: upcoming.opponent || 'Opponent',
      time: upcoming.time || upcoming.date || 'Game Time'
    };
  } catch (e) {
    return null;
  }
}

function toFirestoreValue(val) {
  if (val === null || val === undefined) return { nullValue: null };
  if (typeof val === 'boolean') return { booleanValue: val };
  if (typeof val === 'number') return Number.isInteger(val) ? { integerValue: String(val) } : { doubleValue: val };
  if (Array.isArray(val)) return { arrayValue: { values: val.map(toFirestoreValue) } };
  if (typeof val === 'object') {
    const fields = {};
    Object.keys(val).forEach(k => { fields[k] = toFirestoreValue(val[k]); });
    return { mapValue: { fields } };
  }
  return { stringValue: String(val) };
}

function writeLineupToFirestore(gameId, gameTitle, lineup, dressed) {
  const allIds = Object.keys(ROSTER).map(Number);
  const scratches = dressed.length >= 5 ? allIds.filter(id => !dressed.includes(id)) : [];
  const docUrl =
    'https://firestore.googleapis.com/v1/projects/' +
    CONFIG.FIREBASE_PROJECT_ID +
    '/databases/(default)/documents/lineups/' +
    encodeURIComponent(gameId);

  const payload = {
    fields: {
      game_id: { stringValue: gameId },
      game_title: { stringValue: gameTitle || 'Game' },
      lineup: toFirestoreValue(lineup),
      attendance: toFirestoreValue({
        game_id: gameId,
        dressed: dressed,
        scratches: scratches,
        verified: true,
        source: 'sms_email_bridge',
        calibrated_at: new Date().toISOString()
      })
    }
  };

  UrlFetchApp.fetch(docUrl, {
    method: 'patch',
    contentType: 'application/json',
    payload: JSON.stringify(payload)
  });
}
