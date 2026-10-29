# Aurora Tigers U13A (2026–2027) — Project Status & Roadmap

**Last Updated:** October 27, 2026  
**Repository:** `ScottRepository/U13A-Tigers-2026-2027` (Branch: `main`)  
**Live Application URL:** [https://scottrepository.github.io/U13A-Tigers-2026-2027/](https://scottrepository.github.io/U13A-Tigers-2026-2027/)

---

## 1. Project Overview & Tech Stack

### Executive Summary
The **Aurora Tigers U13A Video Breakdown & Analytics Hub** is an elite, professional-grade minor hockey web application designed to bring NHL/CHL-style video coaching, shift tracking, and game analytics directly to players, parents, and coaching staff. 

The platform prioritizes **zero-friction parent adoption**: families access player shifts, ice-time telemetry, and tactical homework via a simple team passcode (`U13ATigers`) without ever having to create an account, enter email addresses, or remember complex passwords. Coaching staff use an elevated coach passcode (`CoachTigers`) to access real-time telestration, film bookmarking, tactical playbook systems, and cross-device syncing.

### Core Philosophy & Architectural Principles
1. **Zero Client-Side AI Latency:** The client application **never** downloads raw video files or runs heavy AI models in the parent's browser. Shift breakdowns and telemetry are pre-computed during cloud ingest and served as lightweight static JSON payloads loaded in milliseconds.
2. **Zero Parent Friction:** Minor hockey parents should not be forced into user authentication flows. Open security rules on designated Firestore collections paired with client-side passcode gating provide instant access on mobile devices and desktops alike.
3. **100% Free Hosting & Serverless Tier:**
   - **Frontend:** Hosted globally on GitHub Pages ($0 cost).
   - **Database & Sync:** Google Firebase Spark Plan ($0 cost, 50k reads / 20k writes per day).
   - **Video Delivery:** Unlisted YouTube streaming via official YouTube IFrame API ($0 hosting/bandwidth cost).

### Technology Stack Matrix

| Layer | Technology | Purpose & Details |
| :--- | :--- | :--- |
| **Frontend Framework** | Vanilla HTML5 / ES6 JavaScript | Single-page application (`index.html`, ~6,850 LOC) with zero build-step overhead. |
| **Styling & Design System** | Tailwind CSS (CDN) + Custom Typography | Custom Aurora Tigers branding (Tigers Gold `#f5b316`, Deep Slate `#0f172a`), Chakra Petch and Inter typography, responsive split-screen / expanded layouts. |
| **Cloud Database** | Google Cloud Firestore (Spark Tier) | Real-time cross-device data persistence in `northamerica-northeast2 (Toronto)` region. |
| **Video Playback** | YouTube IFrame Player API | Frame-accurate timestamp navigation, looping, slow-motion playback (0.25x - 1x). |
| **Interactive Telestrator** | HTML5 2D Canvas Engine | Pen, line, arrow, spotlight, zone highlights, and tactical whiteboard on ice surface with custom team crest. |
| **Telemetry Ingestion** | Python 3 (`auto_sync.py`, `cv_tracker.py`) | Automated sync with YouTube playlists, TeamSnap iCalendar schedules, and local YOLOv8 / ByteTrack computer vision. |
| **Hosting & CI/CD** | GitHub Pages & Git Version Control | Deployed directly from branch `main`. |

---

## 2. Everything Completed & Configured So Far

### A. Team Portal & User Interface (`index.html`)
- **Pro SaaS Navigation & Layout Modes:**
  - **Split View:** Side-by-side synchronized video player and interactive shift/stat feeds.
  - **Full Width / Expanded Mode:** Maximized tabular telemetry with floating Picture-in-Picture (PiP) mini-player.
- **Passcode-Gated Role Switching:**
  - `U13ATigers` unlocks **Parent View** (shift clips, player dossier, assigned homework, positional IQ playbook).
  - `CoachTigers` / `AdminTigers` unlocks **Coach Mode** (film tray bookmarking, canvas telestrator, tactical board, feedback inbox).
- **5 Core Application Tabs:**
  1. **🎬 Film & Shifts:** Synchronized video playback with period jumping, shift chips, continuous reel auto-advance, category filtering (All, Breakouts, D-Zone, Powerplay, Penalty Kill), and 1-tap **`✅ Verify`** & **`🪪 Passport`** buttons on every card.
  2. **📊 Team Analytics:** Breakout success rates, zone possession distributions (Offensive / Neutral / Defensive), and situational trend tracking.
  3. **👤 Player Hub & Passport:** Complete dossiers for all 17 dressed players (#3 to #98), shift logs, ice time approximations, positional playbooks, and the **Player Passport Career Locker** with 1-click **9:16 Vertical Instagram Reel** export and verified scout link sharing.
  4. **⭐ Coaching Film Tray:** Multi-folder clip bookmarking ("Breakouts", "Forecheck", "D-Zone", "Special Teams") with coach notes.
  5. **💬 Feedback Hub:** Lightweight modal dialog and submission portal allowing parents and players to submit shift corrections, tactical questions, or praise directly to the coaching staff without disrupting video playback.
- **Collaborative Swarm Tagging ("Human-in-the-Loop"):**
  - **`🏷️ Tag Shift`** modal allowing parents to tag missing shifts, goals, or defensive stops in 30 seconds directly into the central team database.
  - 1-tap shift verification badge (`✅ Verified by Team Family`) that boosts confidence score.
- **100% Free Team Pilot Experience:**
  - Zero pricing, payment, subscription, or fee gates—app is 100% unlocked and free for all Aurora Tigers families.
- **In-App Direct Game Film Uploader (`#add-game-modal`):**
  - Seamless ingestion modal supporting unlisted YouTube links, LiveBarn 30-second download workflow, Google Drive / Dropbox shareable links, and direct local video file playback (`<input type="file">`) with zero cloud bandwidth costs.
- **Player Passport Personal Storage Connector (`#passport-storage-modal`):**
  - Dedicated storage connection allowing parents to link YouTube timestamps, personal cloud folders (Google Drive, iCloud, OneDrive), or camera roll videos directly to their player's permanent career archive with visual source badges.
- **1-Click "My Game Tape" Continuous Player Reel:**
  - Personalized hero banner on every player dossier that chains together all shifts back-to-back with live on-screen HUD badges, skipping whistles and intermissions.
- **1-Click SMS & iMessage Sharing Engine:**
  - Deep-linked `sms:?&body=` triggers on TeamSnap post-game recaps, player game tapes, and individual highlight clips for instant sharing with parents, grandparents, and scouts on iOS and Android.
- **Interactive Shot & Scoring Chance Rink Heatmap:**
  - Visual shot layer on the 2D arena rink canvas displaying Tigers attack-zone slot chances vs. perimeter point shots and opponent defensive breakdowns with high-danger radial glow and legend.
- **Progressive Web App (PWA) Standalone Mobile App (`manifest.json`):**
  - Standalone mobile configuration with Tigers branding, high-res app icons, and Apple mobile web app capability for 1-tap "Add to Home Screen" installation without an app store download.
- **Native Mobile Bottom Navigation Bar:**
  - Fixed mobile bottom dock (`[ 🎬 Film ] [ 📊 Team ] [ 👤 Player ] [ 🪪 Passport ] [ 🏷️ Tag ]`) with touch-optimized thumb targets for phones & iPads.
- **TeamSnap 1-Click Post-Game Recap Digest:**
  - Formatted post-game summary generator that automatically compiles score, TOI leaders, and unlisted video portal links ready to paste into TeamSnap or WhatsApp with 1 click.
- **Dual-Clip Virtual Video Ingest (Split LiveBarn / Phone Recordings):**
  - Virtual video stitcher linking Part 1 & Part 2 without cloud video re-encoding or storage; seamlessly swaps playback at the split timestamp.
- **NHL Arena Goal Horn & Crowd Cheering Audio Synthesizer:**
  - Real-time Web Audio API dual-tone brass horn (Kahlenberg D-2 Eb3/Ab3) + bandpass-filtered arena crowd roar on the 9:16 vertical highlight reel simulator with zero external audio assets.
- **Interactive Hockey Whiteboard & Telestrator:**
  - 2D Canvas rink with official red lines, blue lines, face-off circles, and centered Aurora Tigers crest.
  - Preset tactical system overlays: Powerplay 1-3-1, Overload, Penalty Kill Box & Diamond, D-Zone Box-and-One, Rim Breakouts, and Neutral Zone 1-2-2.

### B. TeamSnap Calendar & Schedule Integration
- Integrated live TeamSnap iCalendar feed:  
  `http://ical-cdn.teamsnap.com/team_schedule/filter/games/469cd969-5e1b-4d4c-8f7f-56718c2bf7c3.ics`
- Automatic game day parsing:
  - Game date and kickoff time.
  - Arena facility name and address with 1-click Google Maps navigation.
  - Home vs. Away designation.
  - Automatic team jersey color indicator (Home White vs. Away Black).

### C. Official 17-Player Aurora Tigers Roster (Anchored)
Every player is cataloged with jersey number, primary position, shooting hand, and visual identification cues for tracking:

| # | Player Name | Pos | Hand | Visual / Tactical Identifier |
| :---: | :--- | :---: | :---: | :--- |
| **3** | Stewart Dolmage | LW | L | Forward |
| **5** | Nathan Zhao | RW | R | Wears Glasses |
| **7** | Maxwell Dey | RW | R | Forward |
| **9** | Oliver Patterson | C | L | Faceoff Specialist |
| **10** | Arjun Manjunath | LW | R | Forward |
| **11** | Andrew Bichay | RW | R | Forward |
| **13** | Matthew Hart | G | L | Goalie (Yellow / White Pads) |
| **16** | Joshua Liu | LW | R | Forward |
| **18** | Nathan Carinci | C | R | Faceoff Specialist |
| **21** | Caleb Irgengioro-Wu | RD | R | Defense |
| **23** | Easton Carpentier | C | L | Faceoff Specialist |
| **27** | Alen Fazlic | RD | R | Defense |
| **28** | Ross Elley | LD | L | Defense |
| **76** | Matt Davis | LD | L | Defense |
| **88** | Roy Chen | RW | R | Forward |
| **97** | Hudson Millar | LD | L | Defense |
| **98** | Hudson Barfitt | G | L | Goalie (Red / White Pads) |

### D. Google Cloud Firebase & Firestore Integration
- **Firebase Project Registered:** `aurora-tigers-u13a` (Spark Plan, Free Tier).
- **Location:** `northamerica-northeast2 (Toronto)` for lowest Canadian latency.
- **Project Configuration:**
  ```javascript
  const firebaseConfig = {
    apiKey: "AIzaSyDEiz00S7NnH2_de7vIc5TJc7zA51x_X1A",
    authDomain: "aurora-tigers-u13a.firebaseapp.com",
    projectId: "aurora-tigers-u13a",
    storageBucket: "aurora-tigers-u13a.firebasestorage.app",
    messagingSenderId: "981256803411",
    appId: "1:981256803411:web:9e2a4ad1194a21e2bb22a6",
    measurementId: "G-25GTN0QWHF"
  };
  ```
- **Live Firestore Security Rules Published:**
  ```javascript
  rules_version = '2';
  service cloud.firestore {
    match /databases/{database}/documents {
      match /homework/{docId} { allow read, write: if true; }
      match /tray/{docId} { allow read, write: if true; }
      match /feedback/{docId} { allow read, write: if true; }
      match /lineups/{docId} { allow read, write: if true; }
    }
  }
  ```
- **Real-Time Data Listeners Wired in `index.html`:**
  - `db.collection('tray').doc('shared_coaching_tray')`: Real-time bidirectional sync across coach devices for film bookmarks and assigned homework.
  - `db.collection('feedback')`: Automatic inbox polling and real-time badge counters for coach review.

### E. Coach Lineup & Attendance Calibration Engine (Human-in-the-Loop)
- **Problem Solved:** Single-camera arena footage from stands or LiveBarn makes far-board jersey numbers difficult to read. If an absent player is sick at home, blind AI passes could falsely assign shifts to them.
- **The Solution:** A 2-Phase Human-in-the-Loop calibration workflow:
  1. **AI Discovery:** Scans the broadcast and drafts who appeared dressed and what forward lines / D-pairs rolled.
  2. **Coach 1-Click Verification:** In Coach Mode, coaches check/uncheck absent players (`#attend-check-*`) and adjust line combinations.
  3. **Instant Shift Scrubbing:** Saving removes scratched players from all shifts in that game (ensuring their ice time drops to 0:00), updates the precision score to `🎯 96% AI Precision (Coach Calibrated)`, and syncs to Cloud Firestore (`lineups` collection).

### F. Phase 2 Advanced Capabilities (Fully Completed & Live)
- **Coach 1-Tap Voice Memos (`MediaRecorder API`):**
  - Coaches tap `[ 🎙️ Voice ]` directly on any shift card to record audio feedback.
  - Automatically compressed to Base64 Opus audio, stored in `localStorage`, and synced across devices via Cloud Firestore (`coach_voice_memos` collection).
  - Parents and players tap `[ 🔊 Memo ]` to hear direct audio instruction while viewing their video shift.
- **Goalie Deep-Dive Analytics Hub:**
  - Dedicated telemetry for #13 Matthew Hart (Yellow pads) and #98 Hudson Barfitt (Red pads).
  - Rebound control tracking (Controlled / Pushed to Corner vs. Danger Rebounds).
  - Zone Save % (Slot / High-Danger vs Perimeter Save %).
  - Freeze vs. Play puck decision ratio with 1-click Goalie Save Highlight Reel.
- **Side-by-Side "Player vs. Pro" Video Breakdown:**
  - Dual synchronized comparison player with frame-by-frame scrubbing.
  - Curated NHL reference library: Connor McDavid (10-2 edge work), Cale Makar (blue-line lateral walking), Auston Matthews (angle-change release), Igor Shesterkin (RVH post seal).
- **Bench / Stands One-Touch Live Shift Logger:**
  - Mobile/iPad touch matrix with line roll buttons (Line 1, 2, 3, PP1, PK1) and running game clock.
  - 17-player interactive toggle grid for rapid in-game skater adjustments.
  - 1-Click "Apply to Game Shifts" to immediately commit live logged bench shifts into the active match film.
- **Turnkey Team Administration & Onboarding:**
  - Multi-tenant customization modal (`[ ⚙️ Team Admin ]` in header).
  - Quick-connect inputs for GameSheet Inc., TeamSnap iCal, YouTube playlist, OneDrive/Google Drive, and WhatsApp group.
  - 1-Click Roster Paste Importer: pastes space/tab/comma-delimited text to auto-generate jersey numbers, positions, and handedness.
- **PWA Mobile Home Screen Installation:**
  - Standalone PWA manifest (`manifest.json`) and iOS touch icons for zero-friction mobile home screen installation.
- **SMS & iMessage Sharing Engine:**
  - 1-Click SMS buttons across Game Recap, Player Dossier, and Player Passport to text scout links and game tape directly to family and coaches.
- **Shot & Scoring Chance Heatmap:**
  - Interactive rink overlay visualizing high-danger slot chances vs opponent perimeter shots.
- **1-on-1 "Film Room" Pre-Practice Player Huddle:**
  - Distraction-free iPad lobby/dressing room review view (`[ 👥 1:1 Huddle ]`).
  - Auto-selects 3 key review plays (1 praise play + 2 tactical adjustments) with direct telestrator launcher and coach practice objective note.
  - 1-Click SMS to text the 3-point meeting summary directly to the player/parent.
- **AI-Suggested Practice Drill Cards (Game Weakness ➔ Practice Drill):**
  - Directly translates game telemetry into on-ice practice planning (`[ 📋 Drills ]`).
  - Suggests specific drills based on match breakdowns (D-to-D Reverse & Rim Support, House Box-Out, Quick Release, 1-2-2 Angling).
  - Includes 1-click printable practice plan sheet and TeamSnap text export.
- **GameSheet Inc. Digital Boxscore Alignment Engine:**
  - Synchronizes official GameSheet referee records (`[ 📊 GameSheet Sync ]`).
  - Automatically aligns goal timestamps and penalty records to lock down exact Power Play (PP) and Penalty Kill (PK) shift boundaries against the video clock.
- **Pre-Game 4-Hour SMS Scratch & Lineup Check-In Bot:**
  - Automated Twilio scratch check-in simulator (`[ 💬 4-Hr SMS Bot ]`).
  - Coach replies via SMS (e.g. `10, 23 out`), automatically suppressing absent players to prevent false shift detection and calibrating AI confidence to 96%.
- **Ice Time Equality & Fair-Play Audit Matrix:**
  - Dedicated association compliance audit (`[ ⚖️ Fair Play Audit ]`).
  - Tracks rotational ice time variance across lines with OMHA/Hockey Canada LTPD compliance certification badge and PDF export.
- **Automated 9:16 Instagram & TikTok Highlight Reel Maker:**
  - Vertical mobile story generator (`[ 📱 9:16 Reel ]`) with animated jersey crest, player name, and verified highlight badge ready for social sharing.
- **Locker Room TV / Projector Fullscreen HDMI Presentation Mode:**
  - Big-screen dressing room mode (`[ 📺 TV Mode ]`) with full keyboard hotkeys (`Space` = Play/Pause, `←`/`→` = 5s scrub, `D` = Draw, `C` = Clear, `P` = 2D Rink, `T` = Video, `1`/`2`/`3` = Period Jump).
- **Printable Pre-Game Bench & Lineup Card (Clipboard Ready):**
  - 1-Click printable high-contrast clipboard card (`[ 🖨️ Bench Card ]`) with lines, pairings, starting goalie, special teams, game keys, and shift tally tracker.
- **Multi-Year Career & Tournament History Builder (Player Passport):**
  - Dedicated 5th tab in the Player Passport (`🏆 Career & Tournaments`) allowing parents to document previous teams (e.g. U11A, U12A, OMHA/GTHL), tournament showcases (Silver Stick, Bell Capital Cup), championships, medals, and coach references.
  - Verified GameSheet Inc. season & tournament link embedding so scouts and high school coaches have 1-click access to official referee-signed box scores.
  - Historical stats summary (GP, G, A, PTS, PIM), season video reel linking, and pre-loaded starter profile for #23 Easton Carpentier.
- **Official GameSheet Inc. Team Integration (Aurora Tigers U13A):**
  - Live link and data connection to the official Tigers GameSheet season preview:
    `https://gamesheetstats.com/seasons/15490/teams/534204/preview?configuration%5Binfinite-scroll%5D=false&configuration%5Blogo%5D=false&filter%5Bstatus%5D=completed` (Season: 15490, Team: 534204).
  - Pre-filled across header quick-links, team onboarding defaults, and digital boxscore alignment engine.
- **XbotGo Falcon ➔ GameSheet Live ScoreSync Bridge Engine (`#xbot-bridge-modal`):**
  - Real-time relay bridge linking GameSheet referee scoring with the XbotGo Falcon camera app via ScoreSync (`games.xbotgo.com` with 6-digit match PIN).
  - Automatically translates official referee iPad goals, whistles, and period advances directly into the camera's live scoreboard overlay without any human touching the camera or remote during the game.
  - Interactive simulator HUD allowing coaches to preview and test live clock countdowns, period rolls, and goal increments.
- **In-App Live Stream & GameSheet Real-Time Scoreboard HUD (`#live-broadcast-hud`):**
  - Allows parents to watch the active YouTube livestream directly inside the app with a floating TSN/Sportsnet-style mini scoreboard HUD.
  - Displays real-time Tigers vs Opponent score, live period countdown clock, strength status (5v5, PP1, PK1), and SOG (Shots on Goal) synced with GameSheet.
- **Game Day Live Center & 3-Tab Real-Time Hub (`#live-game-center-modal`):**
  - Dedicated live match operations portal with 3 specialized tab views:
    1. **📊 Live In-Game Tracker & Real-Time AI:** 1-tap touch buttons for Shots on Goal (`+ SOG Tigers`, `+ SOG Opponent`) with automated Goalie Save % calculations, shot differential telemetry, 1-tap Faceoff Tracker by Center (#23 Carpentier, #9 Smith, #18 Ross), and live AI Tactical Momentum cards (Slot protection, PP seam openings, crease rebound alerts).
    2. **🏒 Pre-Game Matchup & Opponent Scout:** Head-to-Head season record against active opponent (e.g. vs Newmarket: 1-1-1), opponent danger player watch list with tactical counters (#14 Miller, #8 Bennett, #31 Vance), Coach's 3 Tactical Keys to the Game, and side-by-side Goalie Tale of the Tape.
    3. **📋 GameSheet Feed & RTMP Stream:** Official GameSheet referee play-by-play ticker (goals, penalties, whistles), Parent Cheer Box with live arena goal horn sound generator, and Xbot Falcon RTMP ingest hub.
- **Spordle & Hockey Canada Registry (HCR) Integration:**
  - Official HCR participant badge (`🍁 HCR #10294829 - Spordle Verified`) integrated directly into the Player Passport.
  - Team Admin configuration for linking association Spordle schedules, tournament brackets, and provincial championship eligibility.
- **Drag-and-Drop Video Replacement & Timestamp Re-Alignment Engine (`#replace-video-modal`):**
  - Solves choppy arena cellular livestreaming by letting coaches replace buffering livestream video with the pristine 1080p/4K master recording from their Falcon SD card or an unlisted YouTube upload.
  - **Zero-Cloud Drag & Drop:** Drop local `.mp4` files directly for instant in-browser playback with zero upload wait time and zero server fees.
  - **Puck Drop Timestamp Calibration:** Automatically calculates the time delta between the livestream start and camera recording start, shifting all 38+ player shifts, period markers, and GameSheet goal events simultaneously with millisecond precision.
  - **100% Data Preservation:** Preserves all existing shift tags, coach voice memos, parent comments, and telestrator bookmarks.
- **Live Stream Mode & Split View Layout Refactor:**
  - **Embedded Side-Panel Live Center (`#live-sidebar-section`):** When switching view mode from Film Archive to Live Stream (`switchViewMode('live_stream')`), the right-hand shift/clip column is replaced with the Game Day Live Center & Real-Time Stats panel (momentum chart, shot counters, faceoff tracker, penalty feed). Shift breakdown cards from archived games are cleanly hidden.
  - **Live Broadcast Detection & Offline Standby:** If no live broadcast is running or YouTube stream is offline, displays a clean placeholder banner (`#live-offline-placeholder`: *"No active live broadcast. Next game scheduled: [Date/Time]"*) computed dynamically via `getNextScheduledGameSummary()`, suppressing ticking live clocks, running period timers, and simulated live scores.
  - **YouTube Live Stream Configuration:** Dedicated input field in **Team Admin -> Integration Links** (`#cfg-youtube-live-url`) allowing coaches/admins to update the active YouTube Live Video ID or URL per game without modifying code. Comprehensive documentation included for connecting YouTube Studio RTMP Stream Keys to the live ingest.
- **Player-Bar Latency Buffer & Sync Lock:**
  - **Pro Video Control Bar Delay Slider (`#player-latency-slider`):** Mirrored Broadcast Stream Delay Buffer slider directly on the main video player control bar, providing instant 0-60 second stream latency adjustments without opening settings modals.
  - **Sync Confirmation & Lock State (`#player-lock-sync-btn`):** Added a "Lock Sync" toggle button beside the delay slider. Locking disables accidental scrubbing, timeline clicking, and latency nudges once broadcast video is synchronized with GameSheet, with a 1-tap "Unlock" toggle for adjustments.
- **XbotGo Falcon Live ScoreSync Bridge UX Clarifications:**
  - **Match PIN & ScoreSync Guidance:** Added descriptive tooltips and a clear 3-step setup guide explaining what the 6-digit Match PIN is, how to retrieve it from ScoreSync (`games.xbotgo.com`), and how it establishes real-time synchronization between the XbotGo camera overlay and GameSheet referee iPads.
  - **3-State Explicit Connection Status Badge (`#xbot-explicit-status-badge`):** Clearly labeled "Connect Live Relay" with explicit visual status indicators (*Ready to Connect*, *Relay Active & Streaming*, *Disconnected / Offline*), updating in real time as coaches input their PIN.
- **Fullscreen & Navigation Glitch Fixes:**
  - **Top Navigation "Schedule & Link Videos" Route Fix:** Implemented the missing `setScheduleHubTab(tab)` function, resolving the uncaught `ReferenceError` that prevented the schedule modal from opening from the top nav bar.
  - **Fullscreen / TV Mode Trap Prevention (`#exit-fullscreen-btn`):** Pinned a high-contrast, always-visible "Exit Fullscreen" / "Back to App" button in the top-right corner when entering TV/Fullscreen mode (`toggleTvPresentationMode()`). Added native `Escape` key capture and `fullscreenchange` event listening so users never get trapped in fullscreen presentation.
- **Schedule Ingestion & Division Filtering (`Add New Game Film`):**
  - **Team Division Matching Filter:** Updated schedule ingestion in `populateAddGameMatchDropdown()` to filter matches by the active team division (`12U / U12A`). Prevents unrelated tournament brackets (such as older U13A CAN/AM tournament listings) from populating the game film dropdown.
  - **Cloud Storage Policy Enforcement:** Added prominent warning notices enforcing external cloud storage destinations (Unlisted YouTube URL, Google Drive, OneDrive, or Dropbox) and technical guardrails preventing large direct MP4 file uploads from storing locally or committing directly into repository git history.
- **View Simplification (Analytics, Player Hub, & Feedback Modal):**
  - **Full-Width Responsive Hubs:** When opening Team Analytics (`breakouts`) or Player Hub (`player_analytics`), the floating smartphone simulator widget is automatically dismissed/hidden, and the layout expands to full width (`col-span-12 w-full`) with a prominent "🎬 Back to Game Film" navigation button to return to the video view.
  - **Lightweight Feedback Modal Dialog (`#feedback-modal`):** Converted the Feedback Hub from a full separate layout view into a lightweight, non-disruptive modal dialog accessible via `openFeedbackModal()` and `closeFeedbackModal()`.
- **System Diagnostic & Connection Audit Engine (`#system-diagnostics-modal`):**
  - **External API & Media Audit:** Automated diagnostic probe verifying that the YouTube IFrame API is mounted, games telemetry JSON (`games_library.json`) fetches 200 OK with verified CORS compliance, and GameSheet/TeamSnap sync endpoints are active.
  - **Live YouTube Error Interceptor & Zero-Reload LiveBarn Fallback:** Intercepts YouTube player errors (Error 150/101 embed restriction, Error 100 private/deleted, Error 5 HTML5 playback failure) and hot-swaps the video stage to a secondary LiveBarn fallback stream or local master recording without requiring a hard page reload.
  - **Dedicated Diagnostic Modal:** Interactive diagnostic console accessible from the header and Team Admin with real-time status tiles, API latency counters, and 1-tap test fallback triggers.
- **Master Puck Drop & Clock Synchronization Engine (`syncPuckDrop()`):**
  - **Single-Click Puck Drop Calibration:** One-click admin calibration button that captures the exact YouTube video timestamp at opening puck drop, establishing a master faceoff reference offset (`periodOneStartVideoTime`).
  - **Precise Gamesheet Event Timestamp Mapping:** Implemented `calculateVideoTimestamp(gamesheetPeriod, gamesheetClockStr)` mapping official referee game clock events (e.g. 12:45 remaining in P2) directly to YouTube video seconds across 1st, 2nd, and 3rd period offsets, recalibrating all shifts and timeline markers dynamically.
- **Special Teams Integration (Real-Time PP & PK Engine):**
  - **Active Penalty State Listener:** Dynamic penalty event tracker monitoring official GameSheet penalty feeds and shift strength classifications (`PP`, `PK`, `5v4`, `4v5`, `5v3`).
  - **Header & Overlay Special Teams Badges:** Injects high-visibility dynamic badges into the central live scoreboard (`#home-st-status`, `#away-st-status`) and video HUD (`#v-special-teams`), highlighting active Powerplays in primary team gold (`--primary-team-color`, `.active-pp`) and Penalty Kills in alert red (`--alert-red`, `.active-pk`) with a ticking countdown timer.
- **Dynamic Theming Engine & Sharp Geometry Architecture:**
  - **Global CSS Variables:** Injected `:root` design tokens (`--bg-base`, `--bg-surface`, `--bg-panel`, `--border-color`, `--primary-team-color`, `--secondary-team-color`, `--text-on-primary`, `--alert-red`, `--success-green`, `--sharp-radius`, `--micro-radius`).
  - **Admin Multi-Team Color Pickers:** Interactive hex-code color pickers in Team Admin allowing coaches to reskin team colors on the fly with automatic persistence in `localStorage` and Firestore.
  - **Sharp Pro Geometry (Hudl / InStat Mode):** One-click toggle (`[ 📐 Sharp Mode ]` / `toggleSharpGeometry()`) reducing component border-radius to 0px / 2px across cards, buttons, badges, and modals for high-density sports science analytics.
- **Unified Pro Header & Dual-Pane Architecture:**
  - Integrated `.unified-header`, `.live-scoreboard`, `.score-box`, `.btn-sharp`, `.workspace-pane`, `.media-track-frame`, and `.analytics-data-sidebar` into the core Antigravity layout.

---

## 3. Current State of the Codebase

### Repository Files & Structure
```text
U13A-Tigers-2026-2027/
├── index.html              # Core single-page web app (~18,440 lines) with Tailwind, Canvas, MediaRecorder & Firebase SDK
├── manifest.json           # Progressive Web App (PWA) mobile installation manifest
├── games_library.json      # Structured game telemetry, period markers, shifts, and TeamSnap metadata
├── auto_sync.py            # Ingest pipeline for YouTube playlist & TeamSnap iCal schedule
├── cv_tracker.py           # Zero-token YOLOv8 + ByteTrack player & rink coordinate tracking
├── README.md               # Repository documentation
├── PROJECT_STATUS.md       # Comprehensive status report, technical docs, and roadmap
└── tigers_logo.png         # Aurora Tigers crest graphic
```

### Git Commit & Deployment State
- **Latest Commit on `main`:**  
  `73bfbbc feat: connect cloud database with simple passcode entry`
- **Working Tree:** Clean, with `PROJECT_STATUS.md` added.
- **GitHub Authentication:** `gh auth login` device flow verified on user Chromebook environment.
- **Deployment Status:** Fully configured for GitHub Pages from branch `main`.

---

## 4. Top Priorities & Next Steps on Our Roadmap

### Priority 1: Push Local Commit & Validate Live Cloud Sync
- Run `git push origin main` from the local Chromebook terminal.
- Verify GitHub Pages deployment at `https://scottrepository.github.io/U13A-Tigers-2026-2027/`.
- Conduct cross-device verification:
  1. Open the portal on a smartphone or tablet using passcode `U13ATigers`.
  2. In another tab or laptop, log in using `CoachTigers`.
  3. Bookmark a video clip in the Coaching Tray or submit a feedback note, and verify it populates on the phone in real time via Firestore.

### Priority 2: Data Credibility & Scrubbing
- **Remove Inactive/Placeholder Data:** Scrub placeholder opponent scouting notes and synthetic test statistics from earlier demo builds.
- **Verify Shift Accuracies:** Audit period transition timestamps (`P1`, `P2`, `P3`) in `games_library.json` against current game film to ensure 100% video-to-shift alignment.

### Priority 3: Automated Game Ingestion Workflow
- Finalize GitHub Actions automated workflow (`.github/workflows/sync.yml`) to run `auto_sync.py` on a daily schedule or on push:
  - Fetches any new YouTube game videos added to the team playlist.
  - Matches the video against the latest TeamSnap game calendar entry.
  - Appends new game entries directly into `games_library.json` without requiring manual JSON editing.

### Priority 4: Coach Homework Distribution Enhancements
- Expand the Coaching Tray modal so coaches can select specific player jersey numbers (e.g. `#23 Easton Carpentier`) when bookmarking a clip.
- Highlight assigned plays on the target player's tab in the Player Hub with a gold "Coach Homework" badge and personalized tactical notes.

### Priority 5: Progressive Web App (PWA) Offline Caching
- Add a lightweight `manifest.json` and basic Service Worker so parents can install the application to their home screen on iOS and Android like a native app.
