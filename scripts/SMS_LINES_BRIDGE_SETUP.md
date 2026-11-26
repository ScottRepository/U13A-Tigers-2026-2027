# Free SMS-to-Email Lineup Bridge (Zero Twilio, Zero New Email)

This lets the coach text game lines directly from his phone's normal SMS/Messages app and automatically loads them into **both** the web portal and the AI video analyzer (`auto_sync.py`) for **$0**.

## 1. No New Email Required (`+lines` Gmail Alias)
Gmail ignores everything after a `+`, so if your email is `yourname@gmail.com`, anything sent to **`yourname+lines@gmail.com`** lands right in your normal inbox and can be matched cleanly.

## 2. 2-Minute Setup in Google Apps Script
1. Open **https://script.google.com** (signed into your existing Google account) → **New Project**.
2. Copy and paste the contents of [`scripts/apps_script_lines_bridge.gs`](apps_script_lines_bridge.gs).
3. *(Optional Pre-Game Reminder)* Set `COACH_SMS_EMAIL` to the coach's Canadian carrier SMS gateway:
   - **Bell / Virgin**: `<10digit>@txt.bell.ca` / `@vmobile.ca`
   - **Rogers**: `<10digit>@pcs.rogers.com`
   - **Telus / Koodo**: `<10digit>@msg.telus.com` / `@msg.koodomobile.com`
   - **Fido**: `<10digit>@fido.ca`
   And set `REPLY_TO_ALIAS` to `yourname+lines@gmail.com`.
4. Click **Triggers (clock icon)** → **Add Trigger**:
   - Function: `syncTextedLinesToFirestore`
   - Event source: **Time-driven** → **Minutes timer** → **Every 5 minutes**.
   - Approve Gmail + external URL permissions once.

## 3. What the Coach Texts
He just texts `yourname+lines@gmail.com` (or replies to your reminder) with either **numbers or names**:
```text
L1: 7 9 11
L2: 23 18 88
L3: 14 19 27
D1: 21 28
D2: 4 12
G: 98
```

## 4. What Happens Automatically
1. Apps Script parses the text and writes it to Cloud Firestore (`lineups/{gameId}`).
2. The web portal ([index.html](../index.html)) pulls it automatically when opening the game and infers missing linemates on shifts.
3. The AI video pipeline ([auto_sync.py](../auto_sync.py)) pulls those exact `verified_lines` + `scratches` from Firestore before analyzing the YouTube film.
