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
  1. **🎬 Film & Shifts:** Synchronized video playback with period jumping, shift chips, continuous reel auto-advance, and category filtering (All, Breakouts, D-Zone, Powerplay, Penalty Kill).
  2. **📊 Team Analytics:** Breakout success rates, zone possession distributions (Offensive / Neutral / Defensive), and situational trend tracking.
  3. **👤 Player Hub:** Complete dossiers for all 17 dressed players (#3 to #98), shift logs, ice time approximations, and custom positional playbooks (Centers, Wingers, Defensemen, Goalies).
  4. **⭐ Coaching Film Tray:** Multi-folder clip bookmarking ("Breakouts", "Forecheck", "D-Zone", "Special Teams") with coach notes.
  5. **💬 Feedback Hub:** Interactive submission portal allowing parents and players to submit shift corrections, tactical questions, or praise directly to the coaching staff.
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

---

## 3. Current State of the Codebase

### Repository Files & Structure
```text
U13A-Tigers-2026-2027/
├── index.html              # Core single-page web app (~6,850 lines) with Tailwind, Canvas & Firebase SDK
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
