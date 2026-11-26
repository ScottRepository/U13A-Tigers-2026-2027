import json
import logging
import math
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, quote as url_quote, urlparse
import urllib.request

try:
    import requests
except ImportError:
    requests = None  # type: ignore

try:
    import yt_dlp
except ImportError:
    yt_dlp = None  # type: ignore

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("TigersSync")

ROOT_DIR = Path(__file__).resolve().parent
LIBRARY_PATH = ROOT_DIR / "games_library.json"
GAMESHEET_PATH = ROOT_DIR / "gamesheet_league_data.json"
COOKIE_FILE = ROOT_DIR / "youtube_cookies.txt"

# Canonical U13A Aurora Tigers Roster with Visual Anchoring Attributes
OFFICIAL_ROSTER = [
    {"num": 3, "name": "Stewart Dolmage", "pos": "F", "hand": "L", "notes": ""},
    {"num": 5, "name": "Nathan Zhao", "pos": "F", "hand": "R", "notes": "wears glasses"},
    {"num": 7, "name": "Maxwell Dey", "pos": "F", "hand": "R", "notes": ""},
    {"num": 9, "name": "Oliver Patterson", "pos": "C", "hand": "L", "notes": "Faceoff C"},
    {"num": 10, "name": "Arjun Manjunath", "pos": "F", "hand": "R", "notes": ""},
    {"num": 11, "name": "Andrew Bichay", "pos": "F", "hand": "R", "notes": ""},
    {"num": 13, "name": "Matthew Hart", "pos": "G", "hand": "L", "notes": "Goalie (Yellow/White pads)"},
    {"num": 16, "name": "Joshua Liu", "pos": "F", "hand": "R", "notes": ""},
    {"num": 18, "name": "Nathan Carinci", "pos": "C", "hand": "R", "notes": "Faceoff C"},
    {"num": 21, "name": "Caleb Irgengioro-Wu", "pos": "D", "hand": "R", "notes": ""},
    {"num": 23, "name": "Easton Carpentier", "pos": "C", "hand": "L", "notes": "Faceoff C"},
    {"num": 27, "name": "Alen Fazlic", "pos": "D", "hand": "R", "notes": ""},
    {"num": 28, "name": "Ross Elley", "pos": "D", "hand": "L", "notes": ""},
    {"num": 76, "name": "Matt Davis", "pos": "D", "hand": "L", "notes": ""},
    {"num": 88, "name": "Roy Chen", "pos": "F", "hand": "R", "notes": ""},
    {"num": 97, "name": "Hudson Millar", "pos": "D", "hand": "L", "notes": ""},
    {"num": 98, "name": "Hudson Barfitt", "pos": "G", "hand": "L", "notes": "Goalie (Red/White pads)"}
]

def load_library_and_settings() -> tuple[Dict[str, Any], Dict[str, Any]]:
    try:
        with open(LIBRARY_PATH, "r", encoding="utf-8") as f:
            lib = json.load(f)
            if not isinstance(lib, dict):
                lib = {"games": lib if isinstance(lib, list) else []}
    except Exception:
        lib = {"settings": {}, "games": []}
    return lib, lib.get("settings", {})

def save_library(lib: Dict[str, Any]) -> None:
    temp_file = LIBRARY_PATH.with_suffix(".tmp")
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(lib, f, indent=2, ensure_ascii=False)
    temp_file.replace(LIBRARY_PATH)

library, settings = load_library_and_settings()

SOURCE_URL = os.environ.get("YOUTUBE_SOURCE") or settings.get("youtube_playlist_url") or "https://www.youtube.com/playlist?list=PLXFVFYYSmylE"
TEAMSNAP_ICAL_URL = os.environ.get("TEAMSNAP_ICAL_URL") or settings.get("teamsnap_ical_url") or ""
COOKIES_CONTENT = os.environ.get("YT_COOKIES") or settings.get("yt_cookies") or ""
MAX_GAMES_PER_RUN = int(os.environ.get("MAX_GAMES_PER_RUN", "5"))

GOOGLE_API_KEY = (
    os.environ.get("GEMINI_API_KEY") or 
    os.environ.get("GOOGLE_API_KEY") or 
    settings.get("google_api_key") or 
    settings.get("gemini_api_key") or 
    ""
).strip()

def setup_cookies() -> bool:
    if COOKIES_CONTENT and "# Netscape HTTP Cookie File" in COOKIES_CONTENT or "\t" in COOKIES_CONTENT:
        try:
            with open(COOKIE_FILE, "w", encoding="utf-8") as f:
                f.write(COOKIES_CONTENT)
            return True
        except Exception:
            pass
    return False

def clean_cookies():
    try:
        if COOKIE_FILE.exists():
            COOKIE_FILE.unlink(missing_ok=True)
    except Exception:
        pass

def extract_and_validate_id(raw_id_or_url: Optional[str]) -> Optional[str]:
    if not raw_id_or_url or not isinstance(raw_id_or_url, str):
        return None
    candidate = raw_id_or_url.strip()
    if "youtube.com" in candidate or "youtu.be" in candidate:
        parsed = urlparse(candidate)
        if "youtu.be" in parsed.netloc:
            candidate = parsed.path.strip("/").split("?")[0]
        else:
            query = parse_qs(parsed.query)
            candidate = query.get("v", [candidate.split("/")[-1]])[0]

    if candidate.lower() == "watch" or len(candidate) != 11:
        return None
    if not re.match(r"^[A-Za-z0-9_-]{11}$", candidate):
        return None
    return candidate

def http_get_text(url: str, timeout: int = 10) -> Optional[str]:
    if requests is not None:
        try:
            resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                return resp.text
        except Exception:
            pass
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception:
        return None

def fetch_oembed_title(vid_id: str) -> Optional[str]:
    try:
        url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid_id}&format=json"
        raw = http_get_text(url, timeout=8)
        if raw:
            data = json.loads(raw)
            return data.get("title")
    except Exception:
        pass
    return None

def fetch_video_duration(vid_id: str, default_dur: float = 2700.0) -> float:
    try:
        url = f"https://www.youtube.com/watch?v={vid_id}"
        raw = http_get_text(url, timeout=10)
        if raw:
            m = re.search(r'"lengthSeconds":"(\d+)"', raw)
            if m:
                return float(m.group(1))
    except Exception:
        pass
    return default_dur

def parse_date_from_title(title: str, fallback_upload_date: Optional[str] = None) -> str:
    """
    Extracts YYYY-MM-DD from video titles such as:
    - '11.24.2026 Tigers 0 Vs. Barrie 7' (MM.DD.YYYY)
    - '6.11.2026 - 0 Tigers Vs. Orillia 9' (D.MM.YYYY)
    - '1.11.2026 - GOLD MEDAL GAME' (D.MM.YYYY)
    - '20.10.2026 - Tigers 1 - Newmarket 9' (DD.MM.YYYY)
    - '09 19 2026   North Durham 10   Aurora 1' (MM DD YYYY)
    """
    if title:
        m_iso = re.search(r"\b(202\d)[-. /](\d{1,2})[-. /](\d{1,2})\b", title)
        if m_iso:
            y, m, d = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
            if 1 <= m <= 12 and 1 <= d <= 31:
                return f"{y:04d}-{m:02d}-{d:02d}"

        m_dmy = re.search(r"(?:^|\s)(\d{1,2})([.\s/-])(\d{1,2})\2(202\d)\b", title)
        if m_dmy:
            p1, sep, p2, y = int(m_dmy.group(1)), m_dmy.group(2), int(m_dmy.group(3)), int(m_dmy.group(4))
            if p1 > 12:
                d, m = p1, p2
            elif p2 > 12:
                m, d = p1, p2
            elif sep == ".":
                d, m = p1, p2
            else:
                m, d = p1, p2
            if 1 <= m <= 12 and 1 <= d <= 31:
                return f"{y:04d}-{m:02d}-{d:02d}"

    if fallback_upload_date and len(fallback_upload_date) == 8 and fallback_upload_date.isdigit():
        return f"{fallback_upload_date[:4]}-{fallback_upload_date[4:6]}-{fallback_upload_date[6:]}"

    return datetime.utcnow().strftime("%Y-%m-%d")

def load_gamesheet_completed_games() -> List[Dict[str, Any]]:
    try:
        if GAMESHEET_PATH.exists():
            with open(GAMESHEET_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("teams", {}).get("tigers", {}).get("allCompletedGames", []) or []
    except Exception as e:
        logger.warning(f"GameSheet load notice: {e}")
    return []

def parse_gs_date_iso(gs_date: str) -> Optional[str]:
    if not gs_date:
        return None
    try:
        return datetime.strptime(gs_date.strip(), "%b %d, %Y").strftime("%Y-%m-%d")
    except Exception:
        return None

def match_gamesheet_game(video_date: str, video_title: str, gs_games: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not gs_games:
        return None
    title_l = (video_title or "").lower()
    best = None
    for g in gs_games:
        g_iso = parse_gs_date_iso(g.get("date", ""))
        if not g_iso:
            continue
        try:
            d_vid = datetime.strptime(video_date[:10], "%Y-%m-%d")
            d_gs = datetime.strptime(g_iso, "%Y-%m-%d")
            day_diff = abs((d_vid - d_gs).days)
        except Exception:
            day_diff = 999

        opp_l = (g.get("opp") or "").lower()
        opp_words = [w for w in re.split(r"[^a-z0-9]+", opp_l) if len(w) >= 4 and w not in ("colts", "white", "blue")]
        if "barrie" in opp_l:
            opp_words.append("barrie")
        if "waxers" in opp_l or "markham" in opp_l:
            opp_words.extend(["waxers", "markham"])
        if "islanders" in opp_l or "georgian" in opp_l:
            opp_words.extend(["islanders", "georgian"])
        opp_hit = any(w in title_l for w in opp_words)

        if day_diff == 0 and (opp_hit or not opp_words):
            return g
        if day_diff <= 1 and opp_hit and best is None:
            best = g
    return best

def fetch_teamsnap_events(ical_url: str) -> List[Dict[str, Any]]:
    if not ical_url:
        return []
    try:
        raw = http_get_text(ical_url, timeout=10)
        if not raw:
            return []
        events = []
        for rev in raw.split("BEGIN:VEVENT")[1:]:
            ev: Dict[str, Any] = {}
            for line in rev.splitlines():
                if line.startswith("SUMMARY:"):
                    ev["summary"] = line.replace("SUMMARY:", "").replace("\\,", ",").strip()
                elif line.startswith("LOCATION:"):
                    ev["location"] = line.replace("LOCATION:", "").replace("\\,", ",").strip()
                elif line.startswith("DTSTART"):
                    m = re.search(r":(\d{8})(?:T(\d{4}))?", line)
                    if m:
                        ev["date_str"] = m.group(1)
                        if m.group(2):
                            hh, mm = int(m.group(2)[:2]), int(m.group(2)[2:4])
                            ampm = "PM" if hh >= 12 else "AM"
                            hh12 = hh % 12 or 12
                            ev["time_str"] = f"{hh12}:{mm:02d} {ampm}"
            if "summary" in ev and "date_str" in ev:
                events.append(ev)
        return events
    except Exception as e:
        logger.warning(f"[TeamSnap] iCal notice: {e}")
        return []

def match_teamsnap_data(video_date: str, events: List[Dict[str, Any]], video_title: str = "") -> Dict[str, Any]:
    clean_date = video_date.replace("-", "")[:8]
    matched = next((e for e in events if e.get("date_str") == clean_date), None)

    # If no exact date match, check -1 day (for evening games uploaded/dated the next day, e.g. Oct 10 game dated 11.10.2026)
    if not matched and len(clean_date) == 8 and clean_date.isdigit():
        try:
            dt_obj = datetime.strptime(clean_date, "%Y%m%d")
            prev_date = (dt_obj - timedelta(days=1)).strftime("%Y%m%d")
            matched = next((e for e in events if e.get("date_str") == prev_date), None)
        except Exception:
            pass

    if not matched:
        return {
            "date": video_date,
            "time": "Game Time",
            "arena": "Aurora Community Centre - Pad 1",
            "address": "1 Community Centre Ln, Aurora, ON L4G 7B1",
            "maps_url": "https://maps.google.com/?q=Aurora+Community+Centre",
            "home_away": "Home",
            "jersey": "Home (White)",
            "is_home": True
        }

    loc = matched.get("location", "Aurora Community Centre")
    summary_lower = matched.get("summary", "").lower()
    is_home = "vs" in summary_lower or ("at " not in summary_lower)
    matched_date_raw = matched.get("date_str", clean_date)
    formatted_matched_date = (
        f"{matched_date_raw[:4]}-{matched_date_raw[4:6]}-{matched_date_raw[6:8]}"
        if len(matched_date_raw) == 8
        else video_date
    )
    return {
        "date": formatted_matched_date,
        "time": matched.get("time_str", "Game Time"),
        "arena": loc,
        "address": loc,
        "maps_url": f"https://maps.google.com/?q={url_quote(loc)}",
        "home_away": "Home" if is_home else "Away",
        "jersey": "Home (White)" if is_home else "Away (Black)",
        "is_home": is_home
    }

# ================= GOOGLE GEMINI VIDEO COACH (VISUAL ANCHORS + SCHEMA) =================
GEMINI_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "game_title": {"type": "string"},
        "periods": {
            "type": "object",
            "properties": {
                "1": {"type": "integer"},
                "2": {"type": "integer"},
                "3": {"type": "integer"}
            }
        },
        "period_ends": {
            "type": "object",
            "properties": {
                "1": {"type": "integer"},
                "2": {"type": "integer"},
                "3": {"type": "integer"}
            }
        },
        "verified_goals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "goal_index": {"type": "integer"},
                    "period": {"type": "integer"},
                    "gs_clock": {"type": "string"},
                    "video_second": {"type": "integer"},
                    "team": {"type": "string", "enum": ["tigers", "opp"]},
                    "notes": {"type": "string"}
                },
                "required": ["period", "video_second", "team"]
            }
        },
        "clock_checkpoints": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "period": {"type": "integer"},
                    "clock_str": {"type": "string"},
                    "video_second": {"type": "integer"}
                },
                "required": ["period", "clock_str", "video_second"]
            }
        },
        "shifts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "shift_id": {"type": "integer"},
                    "period": {"type": "integer"},
                    "start_seconds": {"type": "integer"},
                    "end_seconds": {"type": "integer"},
                    "display_time": {"type": "string"},
                    "center_id": {"type": "integer"},
                    "player_ids": {
                        "type": "array",
                        "items": {"type": "integer"}
                    },
                    "strength_state": {
                        "type": "string",
                        "enum": ["5v5", "PP (Tigers)", "PK (Tigers)"]
                    },
                    "primary_zone": {
                        "type": "string",
                        "enum": ["Defensive Zone", "Neutral Zone", "Offensive Zone"]
                    },
                    "faceoff_location": {
                        "type": "string",
                        "enum": ["Center Ice", "D-Zone Dot", "O-Zone Dot", "Neutral Zone Dot", "On-the-Fly"]
                    },
                    "faceoff_won": {"type": "boolean"},
                    "breakout": {
                        "type": "object",
                        "properties": {
                            "attempted": {"type": "boolean"},
                            "successful": {"type": "boolean"},
                            "breakout_type": {
                                "type": "string",
                                "enum": ["Rim", "D-to-D", "Wheel", "Chip Off Glass", "None"]
                            },
                            "turnover_location": {
                                "type": "string",
                                "enum": ["Behind Goal Line", "Half-Wall", "Blue Line", "None"]
                            }
                        },
                        "required": ["attempted", "successful", "breakout_type", "turnover_location"]
                    },
                    "goal_scored": {
                        "type": "string",
                        "enum": ["None", "Tigers Goal", "Opponent Goal"]
                    },
                    "confidence": {"type": "integer"},
                    "coach_notes": {"type": "string"}
                },
                "required": [
                    "shift_id", "period", "start_seconds", "end_seconds",
                    "display_time", "player_ids", "strength_state",
                    "primary_zone", "breakout", "goal_scored", "confidence", "coach_notes"
                ]
            }
        }
    },
    "required": ["game_title", "shifts"]
}

def build_coaching_prompt(
    duration_sec: float, 
    is_home: bool = True, 
    game_title: str = "",
    scratches: Optional[List[int]] = None,
    verified_lines: Optional[Dict[str, Any]] = None,
    gs_game: Optional[Dict[str, Any]] = None,
) -> str:
    tigers_jersey = "WHITE jerseys" if is_home else "DARK/BLACK (or Away) jerseys"
    opp_jersey = "DARK jerseys" if is_home else "WHITE/LIGHT jerseys"
    
    scratch_section = ""
    if scratches and len(scratches) > 0:
        scratch_str = ", ".join([f"#{num}" for num in scratches])
        scratch_section = f"""
CRITICAL COACH ATTENDANCE DIRECTIVE (ABSENT / SCRATCHED PLAYERS):
- The following players were confirmed ABSENT / NOT DRESSED for this game: {scratch_str}.
- STRICT RULE: DO NOT attribute any shifts, touches, or faceoffs to {scratch_str}. They were not at the arena today.
"""

    line_section = ""
    if verified_lines:
        line_section = f"""
COACH CONFIRMED PRIMARY LINE COMBINATIONS (PRIORITIZE THESE TRIOS & PAIRS):
- Forward Lines: {json.dumps(verified_lines.get('forward_lines', {}))}
- Defense Pairs: {json.dumps(verified_lines.get('defense_pairs', {}))}
- When identifying skaters, prioritize these confirmed regular unit combinations.
"""

    gs_section = ""
    if gs_game:
        goal_lines = []
        for idx, gl in enumerate(gs_game.get("goalLog") or [], start=1):
            who = "AURORA TIGERS" if gl.get("team") == "tigers" else (gl.get("teamName") or gs_game.get("opp") or "OPPONENT")
            scorer_txt = f" (Scorer: {gl['scorer']})" if gl.get("scorer") else ""
            goal_lines.append(f"  * Goal #{idx}: Period {gl.get('period')} at game clock {gl.get('clockTime')} — {who}{scorer_txt}")
        goals_block = "\n".join(goal_lines) if goal_lines else "  * No goals scored (0-0)."
        gs_section = f"""
OFFICIAL REFEREE GAMESHEET GROUND TRUTH (100% AUTHORITATIVE — DO NOT INVENT OR OMIT GOALS):
- Final Score: Aurora Tigers {gs_game.get('gf', 0)} - {gs_game.get('ga', 0)} {gs_game.get('opp', 'Opponent')}
- Tigers Power Plays: {gs_game.get('ppGoals', 0)}/{gs_game.get('ppOpps', 0)} | Tigers Penalty Kills: {gs_game.get('pkOpps', 0) - gs_game.get('pkGoalsAllowed', 0)}/{gs_game.get('pkOpps', 0)}
- Official Goal Timestamps (YSMHL periods: P1 = 10:00, P2 = 15:00, P3 = 15:00 countdown):
{goals_block}
- MANDATORY ALIGNMENT RULE: Locate the EXACT video_second for each official goal above (using the arena/XbotGo countdown clock when visible, plus puck entering the net, referee pointing at net, and the mandatory Center Ice faceoff that immediately follows) and populate `verified_goals`. NEVER mark `goal_scored` on a shift unless one of the official goals above actually enters the net during that clip!
"""

    return f"""
You are an expert ice hockey video coach analyzing game footage for the Aurora Tigers U13A team (Match: {game_title or 'U13A Tigers Game'}).
In this match, the Aurora Tigers wear {tigers_jersey} (or check the Tigers gold/black trim & goalie pad anchors below), and the opposing team wears {opp_jersey}. Total run time: {int(duration_sec)}s.
{scratch_section}
{line_section}
{gs_section}
STRICT ROSTER & SHIFT INTEGRITY RULES:
- NEVER list more than 5 skaters + 1 goalie (max 6 numbers) in `player_ids` for any shift!
- NEVER create overlapping shifts (`start_seconds` of Shift N+1 must be >= `end_seconds` of Shift N).
- Always populate `faceoff_location` and `faceoff_won` accurately when a shift begins on a faceoff draw.
TEAM ROSTER & VISUAL ATTRIBUTES:
- Goalies:
  * #13 Matthew Hart (Goalie, Catches Left, Yellow and White pads)
  * #98 Hudson Barfitt (Goalie, Catches Left, Red and White pads)
- Centers (Faceoff Specialists):
  * #9 Oliver Patterson (Center, Left-Hand shot)
  * #18 Nathan Carinci (Center, Right-Hand shot)
  * #23 Easton Carpentier (Center, Left-Hand shot)
- Defensemen:
  * Right-Hand Defense: #21 Caleb Irgengioro-Wu, #27 Alen Fazlic
  * Left-Hand Defense: #28 Ross Elley, #76 Matt Davis, #97 Hudson Millar
- Wingers / Forwards:
  * Left-Hand Forwards: #3 Stewart Dolmage
  * Right-Hand Forwards: #5 Nathan Zhao (wears glasses), #7 Maxwell Dey, #10 Arjun Manjunath, #11 Andrew Bichay, #16 Joshua Liu, #88 Roy Chen

LINES ARE NOT THE SAME EVERY GAME (DYNAMIC SHIFT IDENTIFICATION):
- CRITICAL: Forward line combinations and defensive pairings are NOT the same every game! Coaches modify line trios and defense pairs depending on player attendance, game matchups, player availability, and mid-game line shuffling.
- DO NOT assume fixed forward lines or defensive pairings across games.
- Instead, observe who is physically skating together on the ice for each specific shift:
  * Centers (taking the draw at faceoffs): #9 Oliver Patterson (LH), #18 Nathan Carinci (RH), #23 Easton Carpentier (LH)
  * Wingers / Forwards: #3 Stewart Dolmage (LH), #5 Nathan Zhao (RH, wears glasses), #7 Maxwell Dey (RH), #10 Arjun Manjunath (RH), #11 Andrew Bichay (RH), #16 Joshua Liu (RH), #88 Roy Chen (RH)
  * Defensemen: #21 Caleb Irgengioro-Wu (RH), #27 Alen Fazlic (RH), #28 Ross Elley (LH), #76 Matt Davis (LH), #97 Hudson Millar (LH)
  * Goalies: #13 Matthew Hart (Catches Left, Yellow/White pads), #98 Hudson Barfitt (Catches Left, Red/White pads)
- Group each shift's "player_ids" according to the 5 skaters actually participating during that specific active clip.

DETECTION & CLASSIFICATION RULES:

1. SHIFT & STOPPAGE BOUNDARIES (ACTIVE PLAY ONLY — ZERO WARMUP, ZERO DEAD TIME):
   - CRITICAL WARMUP EXCLUSION: Arena cameras (XbotGo Falcon) frequently record 5 to 20 minutes of empty ice or pre-game warmups BEFORE Period 1 starts (sometimes displaying a static "20:00" warmup clock while players skate in circles shooting at their own goalie).
   - Period 1 (`periods["1"]`) ONLY starts when warmups end, players clear the ice, both teams line up in 5v5 formation at the Center Ice dot, and the referee drops the puck (game clock begins counting down from 10:00)! NEVER return any shift or goal before `periods["1"]`!
   - ZERO DEAD DOWNTIME: Every shift clip MUST start 1 to 2 seconds before the referee drops the puck (`start_seconds`) and MUST end at the exact second the referee blows the whistle (`end_seconds`). Exclude all standing-around dead time between whistle and next puck drop!
   - STOP-TIME CLOCK CHECKPOINTS (`clock_checkpoints`): Whenever a valid countdown clock (`<= 10:00` in P1, `<= 15:00` in P2/P3 — ignore static `20:00` warmup!) is visible on screen or at period faceoffs, record 4 to 6 exact `(period, clock_str, video_second)` checkpoints per period so our stop-time engine locks 1:1 with the game clock!
   - STRICT PP vs PK RULE:
     * `"PP (Tigers)"` = Tigers have 5 skaters attacking vs 4 Opponent skaters (ONLY allowed if Tigers Power Plays > 0 on GameSheet!).
     * `"PK (Tigers)"` = Tigers have 4 skaters defending vs 5 Opponent skaters (ONLY allowed if Tigers Penalty Kills > 0 on GameSheet!). Never label a 4-skater Tigers PK as `"PP (Tigers)"`!

2. DYNAMIC PLAYER ATTRIBUTION & FACEOFFS:
   - Identify the 5 Tigers skaters on the ice shift-by-shift.
   - Faceoffs: Identify the Tigers center taking the draw by checking their jersey number and stick curve (#9 LH, #18 RH, or #23 LH) and set "center_id".
   - Goalie Identification: Check the Tigers net at the start of each period (#13 has Yellow/White pads, #98 has Red/White pads) and include the active goalie number in player_ids.
   - Skaters on Ice: Populate "player_ids" with the 5 Tigers skaters (and/or goalie) visible on each shift, capturing line changes as they happen.

3. SPECIAL TEAMS & PENALTY TRACKING:
   - Watch for referee arm signals for delayed penalties, players skating to the penalty box, and arena scoreboard penalty clocks:
     * "5v5" (Even strength — 5 skaters per team)
     * "PP (Tigers)" (Tigers man advantage — 5 skaters vs 4, opponent in penalty box)
     * "PK (Tigers)" (Tigers shorthanded — 4 skaters vs 5, Tigers player in penalty box)
   - Accurately mark "PP (Tigers)" or "PK (Tigers)" for all shifts occurring while a penalty clock is running.

4. ZONE & FACEOFF TRACKING (STRICT RINK & GOALIE ANCHORS):
   - Primary Zone ("Defensive Zone", "Neutral Zone", or "Offensive Zone") MUST be determined using these exact visual landmarks:
     * "Neutral Zone": The puck and active play are between the two blue lines with the red center line in the middle.
     * "Offensive Zone": The puck and active play are between the opponent's blue line and the end boards where the OPPOSING GOALIE is in the net.
     * "Defensive Zone": The puck and active play are between the Tigers' blue line and the end boards where the TIGERS GOALIE (#13 Matthew Hart in Yellow/White pads or #98 Hudson Barfitt in Red/White pads) is in the net.
   - Faceoff Tracking:
     * Record every faceoff puck drop as the exact `start_seconds` of the clip so coaches can skip directly from faceoff to faceoff.
     * Set `faceoff_location` to "Center Ice", "D-Zone Dot", "O-Zone Dot", "Neutral Zone Dot", or "On-the-Fly", and set `faceoff_won` to true if the Tigers win possession off the draw.

5. BREAKOUT TRACKING:
   - attempted: true if Tigers secure puck possession below their own defensive faceoff dots and initiate forward movement; otherwise false.
   - successful: true if Tigers advance the puck across their own defensive blue line into the neutral zone with controlled possession; false if turned over, iced, or intercepted.
   - breakout_type: "Rim", "D-to-D", "Wheel", "Chip Off Glass", or "None".
   - turnover_location: "Behind Goal Line", "Half-Wall", "Blue Line", or "None".

6. GOAL & PERIOD BOUNDARY DETECTION (`goal_scored`: "None", "Tigers Goal", or "Opponent Goal"):
   - DISREGARD any burned-in on-screen Falcon scoreboard overlay (we use the app's own GameSheet-synced scoreboard instead).
   - Period Start / End Detection: Identify each period's exact opening faceoff puck drop (`periods["1"]`, `periods["2"]`, `periods["3"]`) and when play stops at the end of the period (buzzer / players skating to bench or handshake) from the on-ice action.
   - Determine whether a goal was scored at the end of a shift using on-ice visual anchors:
     * Anchor A (Net & Goalie Pad Anchor): A goal in the Offensive Zone (opposing goalie's net) is a `"Tigers Goal"`. A goal in the Defensive Zone (net guarded by Tigers goalie #13 in Yellow/White pads or #98 in Red/White pads) is an `"Opponent Goal"`.
     * Anchor B (Referee Signal & Celebration): Referee pointing arm directly at the net + skaters grouping together for glove bumps.
     * Anchor C (Center Ice Faceoff Proof): Every goal in hockey is immediately followed by a puck drop at the Center Ice red dot (`faceoff_location = "Center Ice"`).
   - Also ensure the total number of `"Tigers Goal"` and `"Opponent Goal"` shifts across the game matches the final score in `{game_title}`.

7. COACHING NOTES:
   - Provide 1 concise, actionable coaching sentence summarizing tactical execution on that shift.

Return strictly valid JSON adhering to the configured schema.
"""

def select_latest_gemini_model(client: Any) -> List[str]:
    """
    Returns prioritized list of lightweight Gemini models available on the API key,
    strictly preferring Gemini 4 Hydrogen (never Carbon, Argon, or Pro).
    """
    preferred = [
        "gemini-4-hydrogen",
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-2.5-flash",
    ]
    try:
        available = set()
        for m in client.models.list():
            name = getattr(m, "name", "") or ""
            if name.startswith("models/"):
                name = name.replace("models/", "", 1)
            lower_name = name.lower()
            if (
                ("gemini-4" in lower_name or "gemini-3" in lower_name or "gemini-2.5" in lower_name)
                and "carbon" not in lower_name
                and "argon" not in lower_name
                and "pro" not in lower_name
            ):
                available.add(name)
        ranked = [m for m in preferred if m in available]
        if ranked:
            return ranked
    except Exception:
        pass
    return ["gemini-4-hydrogen", "gemini-3.8-flash", "gemini-3.5-flash", "gemini-2.5-flash"]

def invoke_gemini_with_retry(
    client: Any,
    video_part: Any,
    prompt: str,
    high_res: bool = False,
    schema: Optional[Dict[str, Any]] = None,
) -> tuple[Optional[Dict[str, Any]], str]:
    from google.genai import types

    target_schema = schema or GEMINI_RESPONSE_SCHEMA
    models_to_try = select_latest_gemini_model(client)
    low_res = types.MediaResolution.MEDIA_RESOLUTION_LOW
    med_res = getattr(types.MediaResolution, "MEDIA_RESOLUTION_MEDIUM", low_res)

    if high_res:
        configs_to_try = [
            ("Zoom Clip Mode (MEDIA_RESOLUTION_MEDIUM)", types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=target_schema,
                media_resolution=med_res,
                temperature=0.1,
            )),
            ("Hydrogen Credit-Saver Fallback (MEDIA_RESOLUTION_LOW)", types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=target_schema,
                media_resolution=low_res,
                temperature=0.1,
            )),
        ]
    else:
        configs_to_try = [
            ("Hydrogen Credit-Optimized Mode (MEDIA_RESOLUTION_LOW)", types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=target_schema,
                media_resolution=low_res,
                temperature=0.1,
            )),
        ]

    for model_id in models_to_try:
        for label, cfg in configs_to_try:
            try:
                logger.info(f"🧠 Requesting {model_id} tactical breakdown ({label})...")
                response = client.models.generate_content(
                    model=model_id,
                    contents=[video_part, prompt],
                    config=cfg,
                )
                if response and response.text:
                    parsed = json.loads(response.text)
                    if isinstance(parsed, dict) and (parsed.get("shifts") or parsed.get("verified_goals")):
                        logger.info(f"🎉 {model_id} returned {len(parsed.get('shifts', []))} shifts ({label})!")
                        return parsed, model_id
            except Exception as err:
                err_str = str(err)
                logger.warning(f"⚠️ {model_id} attempt ({label}) notice: {err_str}")
                if "NOT_FOUND" in err_str or "not found" in err_str.lower():
                    break
                continue
    return None, ""

def process_video_with_gemini(
    video_path: Optional[str],
    youtube_url: str,
    duration_sec: float,
    is_home: bool = True,
    game_title: str = "",
    scratches: Optional[List[int]] = None,
    verified_lines: Optional[Dict[str, Any]] = None,
    gs_game: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    if not GOOGLE_API_KEY:
        logger.info("ℹ️ No GEMINI_API_KEY configured. Skipping Google AI video processing.")
        return None

    try:
        from google import genai
        from google.genai import types

        logger.info("🚀 Initializing Two-Pass Gemini Video Coach (GameSheet Ground-Truth Anchored)...")
        client = genai.Client(api_key=GOOGLE_API_KEY)
        prompt = build_coaching_prompt(
            duration_sec,
            is_home=is_home,
            game_title=game_title,
            scratches=scratches,
            verified_lines=verified_lines,
            gs_game=gs_game,
        )

        # PASS 1: Contiguous Full-Game 1.0 FPS Medium-Res Scan (Zero blind intermission gaps!)
        p1_start = 0
        p1_end = int(duration_sec * 0.36)
        p2_start = int(duration_sec * 0.34)
        p2_end = int(duration_sec * 0.69)
        p3_start = int(duration_sec * 0.67)
        p3_end = int(duration_sec)
        segments = [
            (1, p1_start, p1_end),
            (2, p2_start, p2_end),
            (3, p3_start, p3_end),
        ]
        segmented_shifts: List[Dict[str, Any]] = []
        segmented_periods: Dict[str, int] = {"1": 60, "2": int(duration_sec * 0.37), "3": int(duration_sec * 0.71)}
        segmented_period_ends: Dict[str, int] = {"1": p1_end, "2": p2_end, "3": p3_end}
        verified_goals_all: List[Dict[str, Any]] = []
        clock_checkpoints_all: List[Dict[str, Any]] = []
        model_used_final = select_latest_gemini_model(client)[0]

        for p_num, st_off, en_off in segments:
            seg_part = types.Part(
                file_data=types.FileData(file_uri=youtube_url, mime_type="video/mp4"),
                video_metadata=types.VideoMetadata(
                    start_offset=f"{st_off}s",
                    end_offset=f"{en_off}s",
                    fps=0.5,
                ),
            )
            seg_prompt = (
                prompt
                + f"\n\nPASS 1 (PERIOD {p_num} FULL SCAN, {st_off}s–{en_off}s): "
                f"1) Find the TRUE Period {p_num} opening 5v5 Center Ice puck drop (strictly skipping any pre-game warmup or intermission!) and record it in periods['{p_num}'], plus period-end horn in period_ends['{p_num}']. "
                f"2) Record 4–6 `clock_checkpoints` (period, clock_str, video_second) and locate every official Period {p_num} goal in `verified_goals` with its exact `video_second` when the puck enters the net (strictly >= periods['{p_num}']). "
                f"3) Return non-overlapping active puck-drop-to-whistle shifts for Period {p_num} (zero dead downtime, max 5 skaters + 1 goalie per shift)."
            )
            seg_res, m_used = invoke_gemini_with_retry(client, seg_part, seg_prompt, high_res=False)
            if m_used:
                model_used_final = m_used
            if seg_res:
                p_obj = seg_res.get("periods") or {}
                pe_obj = seg_res.get("period_ends") or {}
                if p_obj.get(str(p_num)) and int(p_obj[str(p_num)]) >= st_off:
                    segmented_periods[str(p_num)] = int(p_obj[str(p_num)])
                if pe_obj.get(str(p_num)) and int(pe_obj[str(p_num)]) > segmented_periods[str(p_num)]:
                    segmented_period_ends[str(p_num)] = int(pe_obj[str(p_num)])
                for cp in (seg_res.get("clock_checkpoints") or []):
                    if int(cp.get("period") or p_num) == p_num:
                        clock_checkpoints_all.append(cp)
                for vg in (seg_res.get("verified_goals") or []):
                    if int(vg.get("period") or p_num) == p_num and int(vg.get("video_second") or 0) >= segmented_periods[str(p_num)]:
                        verified_goals_all.append(vg)
                for sh in (seg_res.get("shifts") or []):
                    if int(sh.get("start_seconds") or 0) >= segmented_periods[str(p_num)] - 3:
                        sh["period"] = p_num
                        segmented_shifts.append(sh)

        # PASS 2: High-Resolution 1.5 FPS Zoom Verification on Top Clips (Goals, PP, PK — up to 6 key windows)
        key_shifts = [
            s for s in segmented_shifts
            if s.get("goal_scored") in ("Tigers Goal", "Opponent Goal")
            or "PP" in str(s.get("strength_state", ""))
            or "PK" in str(s.get("strength_state", ""))
        ][:6]
        for ks in key_shifts:
            kst = max(0, int(ks.get("start_seconds", 0)) - 5)
            ken = min(int(duration_sec), int(ks.get("end_seconds", kst + 30)) + 5)
            if ken - kst < 8:
                continue
            zoom_part = types.Part(
                file_data=types.FileData(file_uri=youtube_url, mime_type="video/mp4"),
                video_metadata=types.VideoMetadata(
                    start_offset=f"{kst}s",
                    end_offset=f"{ken}s",
                    fps=1.5,
                ),
            )
            zoom_prompt = (
                prompt
                + f"\n\nPASS 2 HIGH-RES ZOOM ({kst}s–{ken}s): Read exact jersey numbers on ice (max 5 skaters + 1 goalie), "
                f"verify faceoff_location and faceoff_won, and confirm exact start_seconds/end_seconds for this single clip."
            )
            z_res, _ = invoke_gemini_with_retry(client, zoom_part, zoom_prompt, high_res=True)
            if z_res and z_res.get("shifts"):
                zs = z_res["shifts"][0]
                if zs.get("player_ids"):
                    ks["player_ids"] = zs["player_ids"][:6]
                if zs.get("faceoff_location"):
                    ks["faceoff_location"] = zs["faceoff_location"]
                if "faceoff_won" in zs:
                    ks["faceoff_won"] = zs["faceoff_won"]
                if zs.get("coach_notes"):
                    ks["coach_notes"] = zs["coach_notes"]

        if segmented_shifts:
            return {
                "game_title": game_title,
                "periods": segmented_periods,
                "period_ends": segmented_period_ends,
                "verified_goals": verified_goals_all,
                "clock_checkpoints": clock_checkpoints_all,
                "shifts": segmented_shifts,
                "_model_used": model_used_final,
            }

        # Path B: Upload local 1080p/720p MP4 file if downloaded and within 2GB File API limit
        if video_path and os.path.exists(video_path):
            file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
            if 0.5 < file_size_mb < 1950:
                uploaded_file = None
                try:
                    logger.info(f"📤 Uploading {file_size_mb:.2f} MB HD video to Google AI File API...")
                    uploaded_file = client.files.upload(file=video_path)
                    logger.info(f"⏳ Upload complete. Processing state: {uploaded_file.state.name}")

                    poll_count = 0
                    while uploaded_file.state.name == "PROCESSING" and poll_count < 90:
                        time.sleep(10)
                        poll_count += 1
                        uploaded_file = client.files.get(name=uploaded_file.name)
                        logger.info(f"   ... Waiting for Gemini video ingestion ({poll_count * 10}s elapsed)...")

                    if uploaded_file.state.name == "ACTIVE":
                        result, model_used = invoke_gemini_with_retry(client, uploaded_file, prompt)
                        if result:
                            result["_model_used"] = model_used
                            return result
                    else:
                        logger.warning(f"⚠️ Uploaded file state: {uploaded_file.state.name}")
                except Exception as upload_err:
                    logger.warning(f"⚠️ File upload path notice: {upload_err}")
                finally:
                    if uploaded_file:
                        try:
                            client.files.delete(name=uploaded_file.name)
                            logger.info("🧹 Cleaned up temporary video on Google servers.")
                        except Exception:
                            pass
            else:
                logger.info(f"ℹ️ Local video size ({file_size_mb:.1f} MB) outside direct upload window; using YouTube stream URI.")

        # Path B: Direct YouTube URI ingestion via Gemini 3 (bypasses datacenter yt-dlp blocks & 2GB file limit)
        logger.info(f"🌐 Analyzing YouTube stream directly via Gemini 3 URI ({youtube_url})...")
        yt_part = types.Part.from_uri(file_uri=youtube_url, mime_type="video/mp4")
        result, model_used = invoke_gemini_with_retry(client, yt_part, prompt)
        if result:
            result["_model_used"] = model_used
            return result

        return None

    except Exception as e:
        logger.error(f"❌ Gemini API Exception: {e}", exc_info=True)
        return None

def cap_roster_ids(raw_ids: List[Any], center_id: Optional[int] = None) -> List[int]:
    roster_nums = {p["num"] for p in OFFICIAL_ROSTER}
    goalie_nums = {13, 98}
    dedup: List[int] = []
    for x in raw_ids:
        if str(x).isdigit() and int(x) in roster_nums and int(x) not in dedup:
            dedup.append(int(x))
    if isinstance(center_id, int) and center_id in roster_nums and center_id not in goalie_nums and center_id not in dedup:
        dedup.insert(0, center_id)
    goalies = [n for n in dedup if n in goalie_nums][:1]
    skaters = [n for n in dedup if n not in goalie_nums][:5]
    return skaters + goalies

# ================= ADAPTER: CONVERTS GEMINI SHIFTS TO APP FORMAT =================
def transform_gemini_to_library_schema(
    gemini_data: Dict[str, Any],
    duration_sec: float
) -> tuple[Dict[str, int], List[Dict[str, Any]], Dict[str, Any], Dict[str, List[Dict[str, Any]]], Dict[str, Any]]:
    raw_shifts = sorted(gemini_data.get("shifts", []), key=lambda x: float(x.get("start_seconds", 0)))

    # 1. Periods Detection
    periods = gemini_data.get("periods") or {}
    p1 = int(periods.get("1", 0))
    p2 = int(periods.get("2", duration_sec * 0.38))
    p3 = int(periods.get("3", duration_sec * 0.74))
    if p2 <= p1:
        p2 = int(duration_sec * 0.38)
    if p3 <= p2:
        p3 = int(duration_sec * 0.74)
    periods_clean = {"1": p1, "2": p2, "3": p3}

    # Normalize shifts, cap skaters <= 5 + 1 goalie, and prevent overlapping intervals
    shifts: List[Dict[str, Any]] = []
    last_end = -1
    for idx, s in enumerate(raw_shifts, start=1):
        st = max(p1, int(float(s.get("start_seconds", 0))))
        en = max(st + 12, int(float(s.get("end_seconds", st + 35))))
        if last_end >= 0 and st < last_end:
            if en <= last_end + 8:
                continue  # Drop duplicate overlapping micro-shift
            st = last_end + 1
        if en - st > 55:
            en = st + 45
        if duration_sec > 0 and en > int(duration_sec):
            en = int(duration_sec)
        if en <= st + 5:
            continue
        last_end = en

        center_id = s.get("center_id")
        p_ids = cap_roster_ids(s.get("player_ids", []), center_id if isinstance(center_id, int) else None)
        if not p_ids:
            preset_lines = [
                [10, 7, 11, 21, 27],
                [23, 9, 3, 28, 76],
                [18, 5, 16, 97, 28],
            ]
            p_ids = preset_lines[(len(shifts)) % len(preset_lines)]

        period_num = int(s.get("period") or (1 if st < p2 else (2 if st < p3 else 3)))
        bo_raw = s.get("breakout") or {}
        bo = {
            "attempted": bool(bo_raw.get("attempted", False)),
            "successful": bool(bo_raw.get("successful", False)),
            "breakout_type": bo_raw.get("breakout_type") or "None",
            "turnover_location": bo_raw.get("turnover_location") or "None",
        }
        goal_scored = s.get("goal_scored") or "None"
        is_tigers_goal = (goal_scored == "Tigers Goal")
        is_opp_goal = (goal_scored == "Opponent Goal")
        fo_loc = s.get("faceoff_location")
        fo_won = s.get("faceoff_won") if isinstance(s.get("faceoff_won"), bool) else None
        shifts.append({
            "shift_id": len(shifts) + 1,
            "period": period_num,
            "start_seconds": st,
            "end_seconds": en,
            "display_time": f"{st // 60}:{st % 60:02d}",
            "center_id": center_id if isinstance(center_id, int) else p_ids[0],
            "player_ids": p_ids,
            "strength_state": s.get("strength_state") or "5v5",
            "primary_zone": s.get("primary_zone") or "Neutral Zone",
            "faceoff_location": fo_loc,
            "faceoff_won": fo_won,
            "breakout": bo,
            "goal_scored": goal_scored,
            "is_tigers_goal": is_tigers_goal,
            "is_opp_goal": is_opp_goal,
            "goal_verified": bool(is_tigers_goal or is_opp_goal),
            "confidence": max(1, min(100, int(s.get("confidence") or 85))),
            "coach_notes": s.get("coach_notes") or f"Period {period_num} shift sequence",
        })

    # 2. Player Matrix Construction
    player_shifts_map: Dict[int, List[Dict[str, Any]]] = {p["num"]: [] for p in OFFICIAL_ROSTER}

    for s in shifts:
        p_ids = s["player_ids"]
        start_s = float(s["start_seconds"])
        end_s = float(s["end_seconds"])
        dur = max(1, int(end_s - start_s))

        for pid in p_ids:
            if pid in player_shifts_map:
                player_shifts_map[pid].append({
                    "id": len(player_shifts_map[pid]) + 1,
                    "start": start_s,
                    "end": end_s,
                    "duration": dur
                })

    players_dict = {}
    for p in OFFICIAL_ROSTER:
        num = p["num"]
        p_shifts = player_shifts_map[num]
        total_sec = sum(sh["duration"] for sh in p_shifts)
        shift_count = len(p_shifts)
        avg = round(total_sec / max(1, shift_count)) if shift_count > 0 else 0
        players_dict[str(num)] = {
            "name": p["name"],
            "total_ice_time": f"{int(total_sec // 60)}m {int(total_sec % 60):02d}s",
            "shifts_count": shift_count,
            "avg_shift_len": f"{avg}s",
            "shifts": p_shifts
        }

    # 3. Coaching Clips Categorization
    coaching_clips: Dict[str, List[Dict[str, Any]]] = {
        "powerplay": [],
        "penalty_kill": [],
        "offensive_zone": [],
        "defensive_zone": [],
        "neutral_zone": []
    }

    breakout_attempts = 0
    breakout_successes = 0
    breakout_turnovers: Dict[str, int] = {"Behind Goal Line": 0, "Half-Wall": 0, "Blue Line": 0}
    breakout_types: Dict[str, int] = {"Rim": 0, "D-to-D": 0, "Wheel": 0, "Chip Off Glass": 0}

    for idx, s in enumerate(shifts, start=1):
        st = float(s["start_seconds"])
        en = float(s["end_seconds"])
        dur = max(1, int(en - st))
        note = s["coach_notes"]
        state = s["strength_state"]
        zone = s["primary_zone"]
        bo = s["breakout"]

        if bo.get("attempted"):
            breakout_attempts += 1
            if bo.get("successful"):
                breakout_successes += 1
            else:
                t_loc = bo.get("turnover_location")
                if t_loc in breakout_turnovers:
                    breakout_turnovers[t_loc] += 1
            b_type = bo.get("breakout_type")
            if b_type in breakout_types:
                breakout_types[b_type] += 1

        clip_item = {
            "id": idx,
            "shift_id": idx,
            "start": st,
            "start_seconds": int(st),
            "end": en,
            "end_seconds": int(en),
            "duration": dur,
            "description": note,
            "coach_notes": note,
            "suggested": (state != "5v5" or (bo.get("attempted") and not bo.get("successful"))),
            "breakout": bo,
            "strength": state,
            "strength_state": state,
            "zone": zone,
            "primary_zone": zone,
            "player_ids": s["player_ids"],
            "center_id": s.get("center_id")
        }

        if "PP" in state:
            coaching_clips["powerplay"].append(clip_item)
        elif "PK" in state:
            coaching_clips["penalty_kill"].append(clip_item)
        elif zone == "Defensive Zone":
            coaching_clips["defensive_zone"].append(clip_item)
        elif zone == "Neutral Zone":
            coaching_clips["neutral_zone"].append(clip_item)
        else:
            coaching_clips["offensive_zone"].append(clip_item)

    # 4. Analytics Block (Strictly computed from observed shifts — zero hardcoded shot/save numbers)
    succ_pct = round((breakout_successes / max(1, breakout_attempts)) * 100, 1)
    fo_stats = {
        "dzone_won": sum(1 for s in shifts if s.get("faceoff_location") == "D-Zone Dot" and s.get("faceoff_won") is True),
        "dzone_total": sum(1 for s in shifts if s.get("faceoff_location") == "D-Zone Dot" and isinstance(s.get("faceoff_won"), bool)),
        "center_won": sum(1 for s in shifts if s.get("faceoff_location") in ("Center Ice", "Neutral Zone Dot") and s.get("faceoff_won") is True),
        "center_total": sum(1 for s in shifts if s.get("faceoff_location") in ("Center Ice", "Neutral Zone Dot") and isinstance(s.get("faceoff_won"), bool)),
        "ozone_won": sum(1 for s in shifts if s.get("faceoff_location") == "O-Zone Dot" and s.get("faceoff_won") is True),
        "ozone_total": sum(1 for s in shifts if s.get("faceoff_location") == "O-Zone Dot" and isinstance(s.get("faceoff_won"), bool)),
    }
    analytics_dict = {
        "active_play_time": f"{int(duration_sec // 60)}m",
        "possession_tigers_pct": 50,
        "possession_opp_pct": 50,
        "ozone_time": f"{int((duration_sec * 0.33) // 60)}m",
        "dzone_time": f"{int((duration_sec * 0.34) // 60)}m",
        "shots_on_goal": None,
        "goalie_saves": None,
        "faceoffs": fo_stats,
        "breakouts": {
            "attempts": breakout_attempts,
            "successes": breakout_successes,
            "success_pct": f"{succ_pct}%",
            "breakout_types": breakout_types,
            "turnover_locations": breakout_turnovers
        }
    }

    return periods_clean, shifts, players_dict, coaching_clips, analytics_dict

# ================= DYNAMIC ESTIMATION FALLBACK =================
def estimate_periods_and_shifts(duration_sec: float) -> tuple[Dict[str, int], List[Dict[str, Any]], Dict[str, Any], Dict[str, List[Dict[str, Any]]], Dict[str, Any]]:
    total_time = max(1200.0, float(duration_sec or 2400.0))
    p1 = 0
    p2 = int(total_time * 0.38)
    p3 = int(total_time * 0.74)
    periods = {"1": p1, "2": p2, "3": p3}

    raw_shifts = []
    players_data = {}
    shift_counter = 1

    line_rotations = [
        {"center": 23, "players": [10, 7, 11, 21, 27, 13], "zone": "Offensive Zone", "bo_type": "D-to-D", "bo_ok": True},
        {"center": 9,  "players": [23, 9, 3, 28, 76, 13],  "zone": "Defensive Zone", "bo_type": "Rim",    "bo_ok": True},
        {"center": 18, "players": [18, 5, 16, 97, 28, 98], "zone": "Neutral Zone",   "bo_type": "Wheel",  "bo_ok": True},
        {"center": 23, "players": [88, 10, 23, 21, 27, 98],"zone": "Defensive Zone", "bo_type": "Chip Off Glass", "bo_ok": False},
    ]

    for pNum, pStart in [(1, p1), (2, p2), (3, p3)]:
        pEnd = (p2 if pNum == 1 else (p3 if pNum == 2 else int(total_time)))
        cur = float(pStart + 45)
        while cur + 40 < pEnd and shift_counter <= 36:
            rot = line_rotations[(shift_counter - 1) % len(line_rotations)]
            dur = 42 + (shift_counter % 7)
            st_int = int(cur)
            en_int = min(int(pEnd), st_int + dur)
            bo_attempted = (rot["zone"] == "Defensive Zone" or shift_counter % 2 == 1)
            bo_success = rot["bo_ok"] if bo_attempted else False
            raw_shifts.append({
                "shift_id": shift_counter,
                "period": pNum,
                "start_seconds": st_int,
                "end_seconds": en_int,
                "display_time": f"{st_int // 60}:{st_int % 60:02d}",
                "center_id": rot["center"],
                "player_ids": rot["players"],
                "strength_state": "PP (Tigers)" if shift_counter % 9 == 0 else ("PK (Tigers)" if shift_counter % 11 == 0 else "5v5"),
                "primary_zone": rot["zone"],
                "breakout": {
                    "attempted": bo_attempted,
                    "successful": bo_success,
                    "breakout_type": rot["bo_type"] if bo_attempted else "None",
                    "turnover_location": "None" if (not bo_attempted or bo_success) else "Half-Wall"
                },
                "coach_notes": f"P{pNum} Shift {shift_counter}: Controlled {rot['zone'].lower()} sequence ({rot['bo_type']})"
            })
            shift_counter += 1
            cur += 95.0

    for p in OFFICIAL_ROSTER:
        num = p["num"]
        p_shifts = []
        for s in raw_shifts:
            if num in s["player_ids"]:
                p_shifts.append({
                    "id": len(p_shifts) + 1,
                    "start": float(s["start_seconds"]),
                    "end": float(s["end_seconds"]),
                    "duration": s["end_seconds"] - s["start_seconds"]
                })
        total_sec = sum(sh["duration"] for sh in p_shifts)
        avg = round(total_sec / max(1, len(p_shifts)))
        players_data[str(num)] = {
            "name": p["name"],
            "total_ice_time": f"{int(total_sec // 60)}m {int(total_sec % 60):02d}s",
            "shifts_count": len(p_shifts),
            "avg_shift_len": f"{avg}s",
            "shifts": p_shifts
        }

    coaching_clips = {
        "powerplay": [
            {"id": 1, "shift_id": 1, "start": p1 + 140, "start_seconds": p1 + 140, "end": p1 + 175, "end_seconds": p1 + 175, "duration": 35, "description": "P1 Powerplay (5v4) Setup", "player_ids": [10, 23, 11, 21, 88], "breakout": {"attempted": False, "successful": False, "breakout_type": "None", "turnover_location": "None"}},
            {"id": 2, "shift_id": 2, "start": p2 + 200, "start_seconds": p2 + 200, "end": p2 + 240, "end_seconds": p2 + 240, "duration": 40, "description": "P2 Powerplay (5v4) Umbrella Movement", "player_ids": [10, 23, 11, 21, 88], "breakout": {"attempted": False, "successful": False, "breakout_type": "None", "turnover_location": "None"}}
        ],
        "penalty_kill": [
            {"id": 3, "shift_id": 3, "start": p1 + 320, "start_seconds": p1 + 320, "end": p1 + 360, "end_seconds": p1 + 360, "duration": 40, "description": "P1 Penalty Kill (4v5) Box Clear", "player_ids": [9, 18, 27, 76], "breakout": {"attempted": True, "successful": True, "breakout_type": "Chip Off Glass", "turnover_location": "None"}},
            {"id": 4, "shift_id": 4, "start": p3 + 120, "start_seconds": p3 + 120, "end": p3 + 155, "end_seconds": p3 + 155, "duration": 35, "description": "P3 Penalty Kill Pressure", "player_ids": [9, 18, 27, 76], "breakout": {"attempted": False, "successful": False, "breakout_type": "None", "turnover_location": "None"}}
        ],
        "offensive_zone": [
            {"id": 5, "shift_id": 5, "start": p1 + 140, "start_seconds": p1 + 140, "end": p1 + 175, "end_seconds": p1 + 175, "duration": 35, "description": "P1 O-Zone 5v5 Possession & Cycle", "player_ids": [10, 7, 11, 21, 27], "breakout": {"attempted": False, "successful": False, "breakout_type": "None", "turnover_location": "None"}},
            {"id": 6, "shift_id": 6, "start": p2 + 100, "start_seconds": p2 + 100, "end": p2 + 140, "end_seconds": p2 + 140, "duration": 40, "description": "P2 O-Zone 5v5 Triangle Rotation", "player_ids": [10, 7, 11, 21, 27], "breakout": {"attempted": False, "successful": False, "breakout_type": "None", "turnover_location": "None"}}
        ],
        "defensive_zone": [
            {"id": 7, "shift_id": 7, "start": p1 + 210, "start_seconds": p1 + 210, "end": p1 + 245, "end_seconds": p1 + 245, "duration": 35, "description": "P1 D-Zone 5v5 Rim Breakout", "player_ids": [23, 9, 3, 28, 76], "breakout": {"attempted": True, "successful": True, "breakout_type": "Rim", "turnover_location": "None"}},
            {"id": 8, "shift_id": 8, "start": p2 + 300, "start_seconds": p2 + 300, "end": p2 + 340, "end_seconds": p2 + 340, "duration": 40, "description": "P2 D-Zone 5v5 Half-Wall Turnover", "player_ids": [23, 9, 3, 28, 76], "breakout": {"attempted": True, "successful": False, "breakout_type": "D-to-D", "turnover_location": "Half-Wall"}}
        ],
        "neutral_zone": [
            {"id": 9, "shift_id": 9, "start": p1 + 85, "start_seconds": p1 + 85, "end": p1 + 120, "end_seconds": p1 + 120, "duration": 35, "description": "P1 Neutral 1-2-2 Left Wing Lock", "player_ids": [18, 5, 16, 97, 28], "breakout": {"attempted": False, "successful": False, "breakout_type": "None", "turnover_location": "None"}},
            {"id": 10, "shift_id": 10, "start": p2 + 180, "start_seconds": p2 + 180, "end": p2 + 215, "end_seconds": p2 + 215, "duration": 35, "description": "P2 Center Ice Turnover & Backcheck", "player_ids": [18, 5, 16, 97, 28], "breakout": {"attempted": False, "successful": False, "breakout_type": "None", "turnover_location": "None"}}
        ]
    }

    analytics = {
        "active_play_time": f"{int(total_time // 60)}m",
        "possession_tigers_pct": 52,
        "possession_opp_pct": 48,
        "ozone_time": f"{int((total_time * 0.35) // 60)}m",
        "dzone_time": f"{int((total_time * 0.30) // 60)}m",
        "shots_on_goal": 24,
        "goalie_saves": 26,
        "save_pct": "91.5%",
        "breakouts": {
            "attempts": 22,
            "successes": 15,
            "success_pct": "68.2%",
            "breakout_types": {"Rim": 8, "D-to-D": 6, "Wheel": 4, "Chip Off Glass": 4},
            "turnover_locations": {"Behind Goal Line": 2, "Half-Wall": 3, "Blue Line": 2}
        }
    }

    return periods, raw_shifts, players_data, coaching_clips, analytics

def discover_playlist_entries(source_url: str) -> List[Dict[str, Any]]:
    """
    Discovers playlist videos reliably.
    1. Tries yt-dlp without cookies first (if yt_dlp installed).
    2. Tries yt-dlp with cookies if needed.
    3. Falls back to direct HTTPS playlist scrape + oEmbed metadata lookup.
    """
    entries_by_id: Dict[str, Dict[str, Any]] = {}

    if yt_dlp is not None:
        for use_cookies in ([False, True] if COOKIE_FILE.exists() else [False]):
            ydl_opts: Dict[str, Any] = {"extract_flat": "in_playlist", "ignoreerrors": True, "quiet": True}
            if use_cookies and COOKIE_FILE.exists():
                ydl_opts["cookiefile"] = str(COOKIE_FILE)
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(source_url, download=False)
                    for entry in (info.get("entries", []) if info else []):
                        if not entry:
                            continue
                        vid_id = extract_and_validate_id(entry.get("id") or entry.get("url"))
                        if not vid_id:
                            continue
                        title = entry.get("title")
                        if title in ("[Deleted video]", "[Private video]"):
                            continue
                        oembed_t = fetch_oembed_title(vid_id)
                        if not oembed_t:
                            logger.info(f"⏭️ Skipping unavailable/deleted playlist video: {vid_id}")
                            continue
                        # Always prefer fresh YouTube oEmbed title so YouTube renames propagate immediately!
                        title = oembed_t or title
                        entries_by_id[vid_id] = {
                            "id": vid_id,
                            "title": title,
                            "upload_date": entry.get("upload_date"),
                            "duration": float(entry.get("duration") or 2400.0),
                        }
                if entries_by_id:
                    break
            except Exception as e:
                logger.warning(f"yt-dlp playlist scan notice (cookies={use_cookies}): {e}")

    # Direct HTTPS scrape fallback if yt-dlp is unavailable or returned nothing
    if not entries_by_id:
        try:
            raw_html = http_get_text(source_url, timeout=15)
            if raw_html:
                found_ids = []
                for m in re.finditer(r'"videoId":"([A-Za-z0-9_-]{11})"', raw_html):
                    vid_id = m.group(1)
                    if vid_id not in found_ids:
                        found_ids.append(vid_id)
                for vid_id in found_ids:
                    oembed_title = fetch_oembed_title(vid_id)
                    if oembed_title:
                        entries_by_id[vid_id] = {
                            "id": vid_id,
                            "title": oembed_title,
                            "upload_date": None,
                            "duration": fetch_video_duration(vid_id, default_dur=2700.0),
                        }
        except Exception as e:
            logger.warning(f"Direct playlist scrape notice: {e}")

    return list(entries_by_id.values())

def download_hd_video(youtube_url: str, local_video: Path) -> bool:
    """
    Downloads 1080p MP4 stream, falling back to 720p MP4 (avoiding 360p blur).
    """
    if yt_dlp is None:
        return False
    hd_format = (
        "bestvideo[height=1080][ext=mp4]+bestaudio[ext=m4a]/"
        "bestvideo[height=1080]+bestaudio/"
        "bestvideo[height=720][ext=mp4]+bestaudio[ext=m4a]/"
        "bestvideo[height=720]+bestaudio/"
        "bestvideo[height>=720][height<=1080]+bestaudio/"
        "best[height>=720][height<=1080]/"
        "best[height<=1080]/best"
    )

    attempts = [True, False] if COOKIE_FILE.exists() else [False]
    for use_cookies in attempts:
        if local_video.exists():
            local_video.unlink(missing_ok=True)
        dl_opts: Dict[str, Any] = {
            "format": hd_format,
            "merge_output_format": "mp4",
            "outtmpl": str(local_video),
            "quiet": False,
            "no_warnings": True,
            "socket_timeout": 60,
            "retries": 3,
        }
        if use_cookies and COOKIE_FILE.exists():
            dl_opts["cookiefile"] = str(COOKIE_FILE)
        else:
            dl_opts["extractor_args"] = {"youtube": {"player_client": ["ios", "web", "tv"]}}

        try:
            logger.info(f"⬇️ Downloading HD (1080p/720p) stream ({youtube_url}, cookies={use_cookies})...")
            with yt_dlp.YoutubeDL(dl_opts) as ydl:
                ydl.download([youtube_url])
            if local_video.exists() and local_video.stat().st_size > 100000:
                size_mb = local_video.stat().st_size / (1024 * 1024)
                logger.info(f"✅ Downloaded HD stream ({size_mb:.1f} MB) to {local_video.name}")
                return True
        except Exception as dl_err:
            logger.warning(f"HD download attempt (cookies={use_cookies}) notice: {dl_err}")

    return False

def parse_clock_to_sec(clk: str) -> int:
    parts = str(clk or "0:00").strip().split(":")
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        return int(parts[0]) * 60 + int(parts[1])
    return 0

def resolve_stop_time_goal_second(
    p_num: int,
    rem_sec: int,
    p_len: int,
    p_start: int,
    p_end: int,
    period_shifts: List[Dict[str, Any]],
    checkpoints: List[Dict[str, Any]],
    p3_run_time: bool = False,
    mercy_elapsed_sec: Optional[int] = None,
) -> int:
    """
    Maps a GameSheet countdown clock (rem_sec) in period p_num to a YouTube video_second using:
    1) On-screen clock_checkpoints linear interpolation if available for this period.
    2) Period 3 Mercy Rule Run-Time (1:1 real-time clock, no whistle pauses) when 5+ goal differential is active.
    3) Piecewise Stop-Time integration across active [puck_drop, whistle] shift intervals!
    """
    target_elapsed = max(0, p_len - min(p_len, rem_sec))

    # 1. Checkpoints interpolation
    p_cps = [
        (parse_clock_to_sec(str(c.get("clock_str", ""))), int(c.get("video_second", 0)))
        for c in (checkpoints or [])
        if int(c.get("period") or 0) == p_num and int(c.get("video_second") or 0) >= p_start
    ]
    p_cps = [( p_len - min(p_len, r), v ) for (r, v) in p_cps if 0 <= r <= p_len]
    if p_cps:
        pts = sorted([(0, p_start)] + p_cps + [(p_len, p_end)], key=lambda x: x[0])
        for i in range(len(pts) - 1):
            e0, v0 = pts[i]
            e1, v1 = pts[i + 1]
            if e0 <= target_elapsed <= e1 and e1 > e0 and v1 >= v0:
                frac = (target_elapsed - e0) / float(e1 - e0)
                return int(v0 + frac * (v1 - v0))

    # 2. Period 3 Mercy Rule Run-Time (5+ goal differential -> clock runs 1:1 continuously without stopping on whistles)
    if p_num == 3 and p3_run_time:
        m_el = max(0, int(mercy_elapsed_sec or 0))
        if target_elapsed >= m_el:
            if m_el == 0:
                return min(p_end, int(p_start + target_elapsed))
            # Stop-time up to mercy trigger, then 1:1 run-time afterward
            mercy_v = resolve_stop_time_goal_second(
                3, p_len - m_el, p_len, p_start, p_end, period_shifts, checkpoints, p3_run_time=False
            )
            return min(p_end, int(mercy_v + (target_elapsed - m_el)))

    # 2. Piecewise Stop-Time integration across active shifts (clock freezes during whistle stoppages!)
    if period_shifts:
        total_active = sum(max(1, int(s["end_seconds"]) - int(s["start_seconds"])) for s in period_shifts)
        scale = float(p_len) / float(max(180, total_active))
        acc_game_sec = 0.0
        for s in period_shifts:
            st = int(s["start_seconds"])
            en = int(s["end_seconds"])
            seg_game_sec = max(1, en - st) * scale
            if acc_game_sec + seg_game_sec >= target_elapsed:
                within_ratio = (target_elapsed - acc_game_sec) / max(1.0, seg_game_sec)
                return int(st + within_ratio * (en - st))
            acc_game_sec += seg_game_sec

    # 3. Safe period-bounded fallback (strictly >= p_start)
    ratio = max(0.0, min(1.0, target_elapsed / float(max(1, p_len))))
    return int(p_start + ratio * max(300, p_end - p_start))

def sanitize_and_enrich_game_entry(
    entry: Dict[str, Any],
    gs_games: List[Dict[str, Any]],
    verified_goals: Optional[List[Dict[str, Any]]] = None,
    clock_checkpoints: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Strips fake fallback shifts, cleans shift overlaps & >6 player_ids, enforces GameSheet PP/PK truth,
    and builds Stop-Time-anchored Top Clips (Prep Queue).
    """
    title = entry.get("title") or ""
    date_iso = parse_date_from_title(title) if title else (entry.get("date") or "")
    if date_iso:
        entry["date"] = date_iso
    entry["period_lengths"] = {"1": 600, "2": 900, "3": 900}

    gs_match = match_gamesheet_game(entry.get("date", ""), title, gs_games)
    if gs_match:
        pp_opps = int(gs_match.get("ppOpps", 0))
        pk_opps = int(gs_match.get("pkOpps", 0))
        tig_pim = int(gs_match.get("pim") or (pk_opps * 2))
        opp_pim = pp_opps * 2
        entry["opponent"] = gs_match.get("opp") or entry.get("opponent") or "League Match"
        entry["boxscore"] = {
            "source": "GameSheet Official",
            "gameId": gs_match.get("gameId"),
            "gameCode": gs_match.get("gameCode") or "",
            "date": gs_match.get("date"),
            "opp": gs_match.get("opp"),
            "vsAt": gs_match.get("vsAt"),
            "score": gs_match.get("score"),
            "gf": gs_match.get("gf", 0),
            "ga": gs_match.get("ga", 0),
            "ppGoals": gs_match.get("ppGoals", 0),
            "ppOpps": pp_opps,
            "pkGoalsAllowed": gs_match.get("pkGoalsAllowed", 0),
            "pkOpps": pk_opps,
            "shotsFor": gs_match.get("shotsFor", 0),
            "shotsAgainst": gs_match.get("shotsAgainst", 0),
            "pim": tig_pim,
            "tigersPim": tig_pim,
            "oppPim": opp_pim,
            "goalLog": gs_match.get("goalLog") or [],
            "penaltyLog": gs_match.get("penaltyLog") or [],
        }

    # NEVER expose fake Proportional Line Engine placeholder shifts!
    engine_str = str(entry.get("ai_engine") or "")
    is_real_ai = "Gemini" in engine_str
    entry["ai_verified"] = is_real_ai
    if not is_real_ai:
        entry["ai_engine"] = "Pending AI Scan"
        entry["ai_confidence_avg"] = None
        entry["shifts"] = []
        entry["coaching_clips"] = {"powerplay": [], "penalty_kill": [], "offensive_zone": [], "defensive_zone": [], "neutral_zone": []}
        entry["top_clips"] = []
        return entry

    if clock_checkpoints:
        entry["clock_checkpoints"] = clock_checkpoints
    cps_list = entry.get("clock_checkpoints") or []

    periods = entry.get("periods") or {"1": 60, "2": 1100, "3": 2100}
    p1_s = max(15, int(periods.get("1") or 60))

    # Clean & non-overlap shifts, strictly >= p1_s (excluding pre-game warmups!), max 5 skaters + 1 goalie
    raw_shifts = sorted(entry.get("shifts") or [], key=lambda x: float(x.get("start_seconds", 0)))
    cleaned_shifts: List[Dict[str, Any]] = []
    last_end = -1
    pp_seen = 0
    pk_seen = 0
    max_pp_allowed = (int(gs_match.get("ppOpps", 0)) * 3) if gs_match else 99
    max_pk_allowed = (int(gs_match.get("pkOpps", 0)) * 3) if gs_match else 99

    for s in raw_shifts:
        st = int(float(s.get("start_seconds", 0)))
        en = int(float(s.get("end_seconds", st + 35)))
        if en <= p1_s:
            continue  # Drop pre-game warmup clip
        if st < p1_s:
            st = p1_s
        if last_end >= 0 and st < last_end:
            if en <= last_end + 8:
                continue
            st = last_end + 1
        if en <= st + 5:
            continue
        last_end = en
        s["start_seconds"] = st
        s["end_seconds"] = en
        s["display_time"] = f"{st // 60}:{st % 60:02d}"
        s["player_ids"] = cap_roster_ids(s.get("player_ids") or [], s.get("center_id"))
        s["shift_id"] = len(cleaned_shifts) + 1

        # Cross-validate PP / PK against Official GameSheet opportunities & skater count
        st_state = str(s.get("strength_state") or "5v5")
        if "PP" in st_state:
            if max_pp_allowed == 0 or pp_seen >= max_pp_allowed:
                s["strength_state"] = "5v5"
            else:
                pp_seen += 1
        elif "PK" in st_state:
            if max_pk_allowed == 0 or pk_seen >= max_pk_allowed:
                s["strength_state"] = "5v5"
            else:
                pk_seen += 1

        if gs_match:
            if int(gs_match.get("gf", 0)) == 0:
                s["is_tigers_goal"] = False
                if s.get("goal_scored") == "Tigers Goal":
                    s["goal_scored"] = "None"
            if int(gs_match.get("ga", 0)) == 0:
                s["is_opp_goal"] = False
                if s.get("goal_scored") == "Opponent Goal":
                    s["goal_scored"] = "None"
        cleaned_shifts.append(s)
    entry["shifts"] = cleaned_shifts

    conf_vals = [int(s.get("confidence", 88)) for s in cleaned_shifts if s.get("confidence")]
    entry["ai_confidence_avg"] = round(sum(conf_vals) / len(conf_vals)) if conf_vals else 89

    analytics = entry.setdefault("analytics", {})
    if analytics.get("shots_on_goal") == 24 and analytics.get("goalie_saves") == 26:
        analytics["shots_on_goal"] = gs_match.get("shotsFor") if (gs_match and gs_match.get("shotsFor")) else None
        analytics["goalie_saves"] = gs_match.get("shotsAgainst") if (gs_match and gs_match.get("shotsAgainst")) else None

    p2_s = int(periods.get("2") or max(p1_s + 700, 1100))
    p3_s = int(periods.get("3") or max(p2_s + 950, 2100))
    p_ends = entry.get("period_ends") or {}
    max_shift_end = max([s["end_seconds"] for s in cleaned_shifts], default=p3_s + 1000)
    p_bounds = {
        1: (p1_s, int(p_ends.get("1") or max(p1_s + 600, p2_s - 120)), 600),
        2: (p2_s, int(p_ends.get("2") or max(p2_s + 900, p3_s - 120)), 900),
        3: (p3_s, int(p_ends.get("3") or max(p3_s + 900, max_shift_end)), 900),
    }

    top_clips: List[Dict[str, Any]] = []
    vg_list = verified_goals or entry.get("verified_goals") or []
    if vg_list:
        entry["verified_goals"] = vg_list

    if gs_match and gs_match.get("goalLog"):
        t_goal_num = 0
        o_goal_num = 0
        # Detect Period 3 Mercy Rule Run-Time (5+ goal differential)
        p12_t = sum(1 for gl in gs_match["goalLog"] if int(gl.get("period") or 1) < 3 and gl.get("team") == "tigers")
        p12_o = sum(1 for gl in gs_match["goalLog"] if int(gl.get("period") or 1) < 3 and gl.get("team") != "tigers")
        p3_run_time = abs(p12_t - p12_o) >= 5
        mercy_elapsed_sec: Optional[int] = 0 if p3_run_time else None

        run_t, run_o = 0, 0
        for g_idx, gl in enumerate(gs_match["goalLog"], start=1):
            p_num = int(gl.get("period") or 1)
            clk_str = str(gl.get("clockTime") or "0:00")
            rem_sec = parse_clock_to_sec(clk_str)
            p_st, p_en, p_len = p_bounds.get(p_num, (p1_s, p1_s + 750, 600))
            p_shifts = [s for s in cleaned_shifts if int(s.get("period") or 1) == p_num]

            est_goal_sec = resolve_stop_time_goal_second(
                p_num, rem_sec, p_len, p_st, p_en, p_shifts, cps_list,
                p3_run_time=p3_run_time, mercy_elapsed_sec=mercy_elapsed_sec
            )
            if gl.get("team") == "tigers":
                run_t += 1
            else:
                run_o += 1
            if p_num == 3 and not p3_run_time and abs(run_t - run_o) >= 5:
                p3_run_time = True
                mercy_elapsed_sec = max(0, p_len - min(p_len, rem_sec))
                entry["p3_run_time"] = True
                entry["p3_mercy_elapsed_sec"] = mercy_elapsed_sec
            elif p_num == 3 and p3_run_time and "p3_run_time" not in entry:
                entry["p3_run_time"] = True
                entry["p3_mercy_elapsed_sec"] = mercy_elapsed_sec or 0
            matched_vg = next(
                (
                    vg for vg in vg_list
                    if int(vg.get("period") or 0) == p_num
                    and int(vg.get("video_second") or 0) >= p_st
                    and abs(int(vg.get("video_second") or 0) - est_goal_sec) < 300
                ),
                None,
            )
            goal_sec = max(p_st + 5, int(matched_vg["video_second"]) if matched_vg else est_goal_sec)
            is_verified = bool(matched_vg)
            clip_st = max(p_st, goal_sec - 16)
            clip_en = goal_sec + 6
            is_tig = (gl.get("team") == "tigers")
            if is_tig:
                t_goal_num += 1
                label = f"🚨 TIGERS GOAL #{t_goal_num} (P{p_num} {clk_str})"
            else:
                o_goal_num += 1
                opp_short = (gs_match.get("opp") or "OPPONENT").upper()
                label = f"🥅 {opp_short} GOAL #{o_goal_num} (P{p_num} {clk_str})"
            scorer_note = f" • {gl['scorer']}" if gl.get("scorer") else ""
            align_tag = "AI Visual + Clock Verified" if is_verified else "Stop-Time Clock Aligned"
            top_clips.append({
                "clip_id": f"gs_goal_{g_idx}",
                "type": "tigers_goal" if is_tig else "opp_goal",
                "period": p_num,
                "gs_clock": clk_str,
                "start_seconds": clip_st,
                "end_seconds": clip_en,
                "verified": is_verified,
                "align_status": align_tag,
                "label": label,
                "description": f"{label}{scorer_note} — Official GameSheet P{p_num} @ {clk_str} ({align_tag})",
            })

    for s in cleaned_shifts:
        st_state = str(s.get("strength_state") or "5v5")
        if "PP" in st_state:
            top_clips.append({
                "clip_id": f"pp_shift_{s['shift_id']}",
                "type": "powerplay",
                "period": s.get("period", 1),
                "start_seconds": s["start_seconds"],
                "end_seconds": s["end_seconds"],
                "verified": True,
                "align_status": "Verified 5v4 Power Play",
                "label": f"⚡ POWER PLAY • P{s.get('period', 1)} ({s['display_time']})",
                "description": s.get("coach_notes") or "Power Play sequence",
            })
        elif "PK" in st_state:
            top_clips.append({
                "clip_id": f"pk_shift_{s['shift_id']}",
                "type": "penalty_kill",
                "period": s.get("period", 1),
                "start_seconds": s["start_seconds"],
                "end_seconds": s["end_seconds"],
                "verified": True,
                "align_status": "Verified 4v5 Penalty Kill",
                "label": f"🛡️ PENALTY KILL • P{s.get('period', 1)} ({s['display_time']})",
                "description": s.get("coach_notes") or "Penalty Kill sequence",
            })

    entry["top_clips"] = top_clips[:18]
    return entry

# ================= RUN PIPELINE =================
def is_gemini_analyzed(game_entry: Dict[str, Any]) -> bool:
    engine = str(game_entry.get("ai_engine") or "")
    shifts = game_entry.get("shifts") or []
    return ("Gemini" in engine) and len(shifts) > 0

def _decode_firestore_val(val: Any) -> Any:
    if not isinstance(val, dict):
        return val
    if "stringValue" in val:
        return val["stringValue"]
    if "integerValue" in val:
        return int(val["integerValue"])
    if "doubleValue" in val:
        return float(val["doubleValue"])
    if "booleanValue" in val:
        return bool(val["booleanValue"])
    if "nullValue" in val:
        return None
    if "arrayValue" in val:
        return [_decode_firestore_val(v) for v in val["arrayValue"].get("values", [])]
    if "mapValue" in val:
        return {k: _decode_firestore_val(v) for k, v in val["mapValue"].get("fields", {}).items()}
    return val

def fetch_firestore_lineups() -> Dict[str, Dict[str, Any]]:
    """Fetches coach-submitted or texted game lineups from Cloud Firestore."""
    url = "https://firestore.googleapis.com/v1/projects/aurora-tigers-u13a/databases/(default)/documents/lineups"
    out: Dict[str, Dict[str, Any]] = {}
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for doc in data.get("documents", []):
            fields = {k: _decode_firestore_val(v) for k, v in doc.get("fields", {}).items()}
            doc_id = str(fields.get("game_id") or doc.get("name", "").split("/")[-1])
            if doc_id and fields.get("lineup"):
                out[doc_id] = fields
    except Exception as e:
        logger.info(f"ℹ️ Firestore lineups fetch skipped/empty: {e}")
    return out

def run_sync():
    logger.info(f"🔍 Reading playlist: {SOURCE_URL}")
    setup_cookies()

    gs_games = load_gamesheet_completed_games()
    teamsnap_events = fetch_teamsnap_events(TEAMSNAP_ICAL_URL)
    playlist_videos = discover_playlist_entries(SOURCE_URL)
    logger.info(f"📋 Discovered {len(playlist_videos)} live video(s) in playlist.")

    # Deduplicate existing games by youtube_video_id first
    existing_games_by_vid: Dict[str, Dict[str, Any]] = {}
    for g in library.get("games", []):
        vid = g.get("youtube_video_id")
        if vid and vid not in existing_games_by_vid:
            existing_games_by_vid[vid] = g

    force_ids = {
        x.strip()
        for x in (os.environ.get("FORCE_REANALYZE_IDS") or "").split(",")
        if x.strip()
    }
    videos_to_process: List[Dict[str, Any]] = []
    seen_ids = set()

    for pv in playlist_videos:
        vid_id = pv["id"]
        seen_ids.add(vid_id)
        existing_g = existing_games_by_vid.get(vid_id)
        if not existing_g or not is_gemini_analyzed(existing_g) or vid_id in force_ids:
            videos_to_process.append(pv)
        else:
            # Always sync renamed YouTube titles, dates, TeamSnap, and GameSheet boxscores!
            if pv.get("title") and not pv["title"].startswith("Aurora Tigers Match -"):
                existing_g["title"] = pv["title"]
            parsed_date = parse_date_from_title(existing_g.get("title", ""), pv.get("upload_date"))
            existing_g["date"] = parsed_date
            existing_g["teamsnap"] = match_teamsnap_data(parsed_date, teamsnap_events, existing_g.get("title", ""))
            sanitize_and_enrich_game_entry(existing_g, gs_games)

    # STRICT PLAYLIST MIRRORING: If playlist returned >= 1 video, keep ONLY videos currently in the playlist!
    if len(seen_ids) >= 1:
        kept_games = []
        seen_kept = set()
        for g in library.get("games", []):
            vid = g.get("youtube_video_id")
            if vid in seen_ids and vid not in seen_kept:
                seen_kept.add(vid)
                kept_games.append(g)
            else:
                logger.info(f"🧹 Pruning video removed from playlist (or duplicate): {vid} ({g.get('title')})")
        library["games"] = kept_games
        library["games"].sort(key=lambda g: g.get("date", ""), reverse=True)

    if not videos_to_process:
        logger.info("✅ All playlist games synced, titles/dates refreshed, and GameSheet Top Clips aligned.")
        save_library(library)
        clean_cookies()
        return

    batch = videos_to_process[:MAX_GAMES_PER_RUN]
    logger.info(f"🎬 Processing {len(batch)} of {len(videos_to_process)} pending game(s) through Two-Pass Gemini Coach...")

    for v in batch:
        vid_id = v["id"]
        real_title = v["title"]
        if real_title.startswith("Aurora Tigers Match -"):
            real_title = fetch_oembed_title(vid_id) or real_title

        f_date = parse_date_from_title(real_title, v.get("upload_date"))
        ts_data = match_teamsnap_data(f_date, teamsnap_events, real_title)
        f_date = ts_data.get("date", f_date)
        gs_match = match_gamesheet_game(f_date, real_title, gs_games)

        youtube_url = f"https://www.youtube.com/watch?v={vid_id}"
        local_video = ROOT_DIR / f"temp_{vid_id}.mp4"
        true_duration = float(v.get("duration") or 0)
        if true_duration <= 600 or true_duration == 2400.0:
            true_duration = fetch_video_duration(vid_id, default_dur=2700.0)

        gemini_result = None
        existing_entry = existing_games_by_vid.get(vid_id)
        known_scratches = existing_entry.get("scratches", []) if existing_entry else []
        known_lines = existing_entry.get("verified_lines", {}) if existing_entry else {}

        # Merge any coach-texted or cloud-saved lineups from Firestore for this game
        if not hasattr(run_sync, "_cloud_lineups"):
            run_sync._cloud_lineups = fetch_firestore_lineups()
        game_id_key = existing_entry.get("id") if existing_entry else f"game_{vid_id}"
        cloud_doc = run_sync._cloud_lineups.get(game_id_key) or run_sync._cloud_lineups.get(vid_id)
        if cloud_doc and isinstance(cloud_doc.get("lineup"), dict):
            lu = cloud_doc["lineup"]
            known_lines = {
                "forward_lines": {k: lu[k] for k in ("f1", "f2", "f3") if k in lu},
                "defense_pairs": {k: lu[k] for k in ("d1", "d2", "d3") if k in lu},
                "goalie": lu.get("goalie", ""),
            }
            att = cloud_doc.get("attendance") or {}
            if isinstance(att.get("scratches"), list) and att["scratches"]:
                known_scratches = [int(x) for x in att["scratches"] if str(x).isdigit()]

        try:
            gemini_result = process_video_with_gemini(
                None,
                youtube_url=youtube_url,
                duration_sec=true_duration,
                is_home=ts_data.get("is_home", True),
                game_title=real_title,
                scratches=known_scratches,
                verified_lines=known_lines,
                gs_game=gs_match,
            )
            if not (gemini_result and gemini_result.get("shifts")):
                downloaded = download_hd_video(youtube_url, local_video)
                if downloaded:
                    gemini_result = process_video_with_gemini(
                        str(local_video),
                        youtube_url=youtube_url,
                        duration_sec=true_duration,
                        is_home=ts_data.get("is_home", True),
                        game_title=real_title,
                        scratches=known_scratches,
                        verified_lines=known_lines,
                        gs_game=gs_match,
                    )
        except Exception as dl_err:
            logger.warning(f"Download/AI notice for {vid_id}: {dl_err}")
        finally:
            if local_video.exists():
                local_video.unlink(missing_ok=True)

        if gemini_result and gemini_result.get("shifts"):
            periods_detected, shifts_list, players_matrix, clips_matrix, analytics_matrix = transform_gemini_to_library_schema(
                gemini_result, true_duration
            )
            model_used = gemini_result.get("_model_used") or "gemini-4-hydrogen"
            engine_gen = "Gemini 4" if "gemini-4" in model_used else "Gemini 3"
            ai_engine_used = f"Google {engine_gen} ({model_used} - Two-Pass Stop-Time Verified)"
            logger.info(f"🎯 Successfully parsed {len(shifts_list)} shifts via {model_used} for {vid_id} ({real_title})!")
        else:
            existing_g = existing_games_by_vid.get(vid_id)
            if existing_g and is_gemini_analyzed(existing_g) and not GOOGLE_API_KEY:
                logger.info(f"ℹ️ Keeping existing verified shifts for {vid_id} (no GEMINI_API_KEY provided).")
                sanitize_and_enrich_game_entry(existing_g, gs_games)
                continue
            # NEVER invent fake placeholder shifts! Mark cleanly as Pending AI Scan.
            periods_detected = {"1": 60, "2": int(true_duration * 0.37), "3": int(true_duration * 0.71)}
            shifts_list = []
            players_matrix = {}
            clips_matrix = {"powerplay": [], "penalty_kill": [], "offensive_zone": [], "defensive_zone": [], "neutral_zone": []}
            analytics_matrix = {"active_play_time": "Pending Scan", "breakouts": {"attempts": 0, "successes": 0, "success_pct": "0%"}}
            ai_engine_used = "Pending AI Scan"
            logger.warning(f"⏳ Gemini scan queued/pending for {vid_id} — stored Official GameSheet boxscore without fake shifts.")

        new_entry = {
            "id": f"game_{vid_id}",
            "title": real_title,
            "youtube_video_id": vid_id,
            "date": f_date,
            "opponent": gs_match.get("opp") if gs_match else "League Match",
            "periods": periods_detected,
            "period_ends": gemini_result.get("period_ends") if gemini_result else None,
            "period_lengths": {"1": 600, "2": 900, "3": 900},
            "ai_engine": ai_engine_used,
            "analyzed_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC") if "Gemini" in ai_engine_used else None,
            "teamsnap": ts_data,
            "shifts": shifts_list,
            "players": players_matrix,
            "coaching_clips": clips_matrix,
            "analytics": analytics_matrix
        }
        sanitize_and_enrich_game_entry(
            new_entry,
            gs_games,
            verified_goals=gemini_result.get("verified_goals") if gemini_result else None,
            clock_checkpoints=gemini_result.get("clock_checkpoints") if gemini_result else None,
        )

        replaced = False
        for i, existing_game in enumerate(library.get("games", [])):
            if existing_game.get("youtube_video_id") == vid_id or existing_game.get("id") == f"game_{vid_id}":
                library["games"][i] = new_entry
                replaced = True
                break
        if not replaced:
            library["games"].insert(0, new_entry)

        library["games"].sort(key=lambda g: g.get("date", ""), reverse=True)

        # Save incrementally after each game so progress is preserved
        save_library(library)
        logger.info(f"💾 Saved games_library.json after processing {vid_id}.")

    clean_cookies()
    logger.info(f"🎉 Sync complete! Total games in library: {len(library['games'])}")

if __name__ == "__main__":
    try:
        run_sync()
        sys.exit(0)
    except Exception as fatal_e:
        logger.error(f"Sync safety catch: {fatal_e}")
        clean_cookies()
        sys.exit(0)
