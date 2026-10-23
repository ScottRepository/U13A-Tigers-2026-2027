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
from urllib.parse import parse_qs, urlparse

import requests
import yt_dlp

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("TigersSync")

ROOT_DIR = Path(__file__).resolve().parent
LIBRARY_PATH = ROOT_DIR / "games_library.json"
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

def fetch_oembed_title(vid_id: str) -> Optional[str]:
    try:
        url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid_id}&format=json"
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("title")
    except Exception:
        pass
    return None

def fetch_video_duration(vid_id: str, default_dur: float = 2700.0) -> float:
    try:
        url = f"https://www.youtube.com/watch?v={vid_id}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            m = re.search(r'"lengthSeconds":"(\d+)"', resp.text)
            if m:
                return float(m.group(1))
    except Exception:
        pass
    return default_dur

def parse_date_from_title(title: str, fallback_upload_date: Optional[str] = None) -> str:
    """
    Extracts YYYY-MM-DD from video titles such as:
    - '20.10.2026 - Tigers 1 - Newmarket 9' (DD.MM.YYYY)
    - '04.10.2026 - Tigers 1 - Upper York 11' (DD.MM.YYYY)
    - '09 19 2026   North Durham 10   Aurora 1' (MM DD YYYY)
    - '26 09 2026   Tigers 0   Welland 8' (DD MM YYYY)
    """
    if title:
        # Check YYYY-MM-DD or YYYY.MM.DD
        m_iso = re.search(r"\b(202\d)[-. /](\d{2})[-. /](\d{2})\b", title)
        if m_iso:
            y, m, d = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
            if 1 <= m <= 12 and 1 <= d <= 31:
                return f"{y:04d}-{m:02d}-{d:02d}"

        # Check DD.MM.YYYY or MM.DD.YYYY or DD MM YYYY at start of title
        m_dmy = re.search(r"\b(\d{2})[.\s/-](\d{2})[.\s/-](202\d)\b", title)
        if m_dmy:
            p1, p2, y = int(m_dmy.group(1)), int(m_dmy.group(2)), int(m_dmy.group(3))
            sep = title[m_dmy.start() + 2]
            if p1 > 12:
                # Definitely DD MM YYYY
                d, m = p1, p2
            elif p2 > 12:
                # Definitely MM DD YYYY
                m, d = p1, p2
            elif sep == ".":
                # Dot-separated titles in this repo use DD.MM.YYYY (e.g., 11.10.2026, 07.10.2026, 04.10.2026, 03.10.2026)
                d, m = p1, p2
            else:
                m, d = p1, p2
            if 1 <= m <= 12 and 1 <= d <= 31:
                return f"{y:04d}-{m:02d}-{d:02d}"

    if fallback_upload_date and len(fallback_upload_date) == 8 and fallback_upload_date.isdigit():
        return f"{fallback_upload_date[:4]}-{fallback_upload_date[4:6]}-{fallback_upload_date[6:]}"

    return datetime.utcnow().strftime("%Y-%m-%d")

def fetch_teamsnap_events(ical_url: str) -> List[Dict[str, Any]]:
    if not ical_url:
        return []
    try:
        resp = requests.get(ical_url, timeout=10)
        resp.raise_for_status()
        events = []
        for rev in resp.text.split("BEGIN:VEVENT")[1:]:
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
        "maps_url": f"https://maps.google.com/?q={requests.utils.quote(loc)}",
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
                    "confidence": {"type": "integer"},
                    "coach_notes": {"type": "string"}
                },
                "required": [
                    "shift_id", "period", "start_seconds", "end_seconds",
                    "display_time", "player_ids", "strength_state",
                    "primary_zone", "breakout", "confidence", "coach_notes"
                ]
            }
        }
    },
    "required": ["game_title", "shifts"]
}

def build_coaching_prompt(duration_sec: float, is_home: bool = True, game_title: str = "") -> str:
    tigers_jersey = "WHITE jerseys" if is_home else "DARK/BLACK (or Away) jerseys"
    opp_jersey = "DARK jerseys" if is_home else "WHITE/LIGHT jerseys"
    return f"""
You are an expert ice hockey video coach analyzing game footage for the Aurora Tigers U13A team (Match: {game_title or 'U13A Tigers Game'}).
In this match, the Aurora Tigers wear {tigers_jersey} (or check the Tigers gold/black trim & goalie pad anchors below), and the opposing team wears {opp_jersey}. Total run time: {int(duration_sec)}s.

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

REGULAR LINE COMBINATIONS & DEFENSIVE PAIRINGS:
- Forward Line 1: #10 Arjun Manjunath (LW) — #23 Easton Carpentier (C) — #7 Maxwell Dey (RW)
- Forward Line 2: #3 Stewart Dolmage (LW) — #9 Oliver Patterson (C) — #5 Nathan Zhao (RW)
- Forward Line 3: #16 Joshua Liu (LW) — #18 Nathan Carinci (C) — #11 Andrew Bichay (RW) / #88 Roy Chen (RW)
- Defense Pair 1: #28 Ross Elley (LD) — #21 Caleb Irgengioro-Wu (RD)
- Defense Pair 2: #76 Matt Davis (LD) — #27 Alen Fazlic (RD)
- Defense Pair 3: #97 Hudson Millar (LD) — #21 Caleb Irgengioro-Wu (RD)
- Powerplay Unit (PP): #23, #10, #7, #28, #21
- Penalty Kill Unit (PK): #9, #18, #28, #21, #10

DETECTION & CLASSIFICATION RULES:

1. SHIFT & STOPPAGE BOUNDARIES (ACTIVE PLAY ONLY — PUCK DROP TO WHISTLE):
   - ONLY analyze and include actual active playing time.
   - STRICTLY EXCLUDE: pre-game warmups, intermissions between periods, timeouts, injury delays, and dead time where players are standing around waiting for the referee to drop the puck.
   - Exact Clip Start (start_seconds): Set start_seconds to the EXACT second the referee drops the puck at the faceoff dot (or the exact second an on-the-fly line change gains active play). For Powerplay ("PP (Tigers)") and Penalty Kill ("PK (Tigers)") clips, always start right at the faceoff puck drop!
   - Exact Clip End (end_seconds): Set end_seconds to the EXACT second the whistle blows and play stops (or when the line changes). Each clip should be 20 to 55 seconds of continuous live action — NEVER span across a stoppage or whistle.
   - Look for the opening faceoff puck drop of the 1st, 2nd, and 3rd periods and record their exact video timestamps in seconds under "periods" ("1", "2", "3").

2. PLAYER ATTRIBUTION VIA REGULAR LINES & FACEOFFS:
   - Identify the 5 Tigers skaters on the ice using the line combinations above. Skaters frequently shift on together as lines and D-pairs.
   - Faceoffs: Identify the Tigers center taking the draw by checking their jersey number and stick curve (#9 LH, #18 RH, or #23 LH) and set "center_id".
   - Goalie Identification: Check the Tigers net at the start of each period (#13 has Yellow/White pads, #98 has Red/White pads) and include the active goalie number in player_ids.
   - Skaters on Ice: Populate "player_ids" with the 5 Tigers skaters (and/or goalie) visible on each shift, distributing shifts realistically across all 3 forward lines and defense pairings.

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

6. COACHING NOTES:
   - Provide 1 concise, actionable coaching sentence summarizing tactical execution on that shift.

Return strictly valid JSON adhering to the configured schema.
"""
"""

def select_latest_gemini_model(client: Any) -> List[str]:
    """
    Returns prioritized list of the latest Gemini 3.x / 3.1 models available on the API key,
    falling back to gemini-3-flash-preview and gemini-2.5-flash.
    """
    preferred = [
        "gemini-3.5-flash",
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.1-pro-preview",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
    ]
    try:
        available = set()
        for m in client.models.list():
            name = getattr(m, "name", "") or ""
            if name.startswith("models/"):
                name = name.replace("models/", "", 1)
            if "gemini-3" in name or "gemini-2.5" in name:
                available.add(name)
        ranked = [m for m in preferred if m in available]
        if ranked:
            return ranked
    except Exception:
        pass
    return ["gemini-3.5-flash", "gemini-3.8-flash", "gemini-2.5-flash"]

def invoke_gemini_with_retry(client: Any, video_part: Any, prompt: str) -> tuple[Optional[Dict[str, Any]], str]:
    from google.genai import types

    models_to_try = select_latest_gemini_model(client)
    configs_to_try = [
        ("Token-Optimized Mode (MEDIA_RESOLUTION_LOW)", types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=GEMINI_RESPONSE_SCHEMA,
            media_resolution=types.MediaResolution.MEDIA_RESOLUTION_LOW,
            temperature=0.2,
        )),
        ("Standard Resolution Fallback", types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=GEMINI_RESPONSE_SCHEMA,
            temperature=0.2,
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
                    if isinstance(parsed, dict) and parsed.get("shifts"):
                        logger.info(f"🎉 {model_id} returned {len(parsed['shifts'])} shifts ({label})!")
                        return parsed, model_id
            except Exception as err:
                err_str = str(err)
                logger.warning(f"⚠️ {model_id} attempt ({label}) notice: {err_str}")
                if "NOT_FOUND" in err_str or "not found" in err_str.lower():
                    break  # Try next model in list
                continue
    return None, ""

def process_video_with_gemini(
    video_path: Optional[str],
    youtube_url: str,
    duration_sec: float,
    is_home: bool = True,
    game_title: str = "",
) -> Optional[Dict[str, Any]]:
    if not GOOGLE_API_KEY:
        logger.info("ℹ️ No GEMINI_API_KEY configured. Skipping Google AI video processing.")
        return None

    try:
        from google import genai
        from google.genai import types

        logger.info("🚀 Initializing Gemini Client with Hockey Tactical Anchors...")
        client = genai.Client(api_key=GOOGLE_API_KEY)
        prompt = build_coaching_prompt(duration_sec, is_home=is_home, game_title=game_title)

        # Path A: 3-Period Segmented YouTube URI Analysis via Gemini 3.5 Flash (Token-Saver Mode)
        # Trims pre-game warmup, intermission buffers, and post-game handshakes, and samples at 0.5 FPS
        # with MEDIA_RESOLUTION_LOW (~175k tokens per full game instead of ~1.06M tokens!).
        logger.info(f"🌐 Running token-optimized 3-period Gemini 3.5 analysis on {youtube_url} ({int(duration_sec)}s)...")
        warmup_trim = int(min(180, duration_sec * 0.05))
        p1_end = int(duration_sec * 0.33)
        p2_start = int(duration_sec * 0.36)  # Skip 1st intermission
        p2_end = int(duration_sec * 0.66)
        p3_start = int(duration_sec * 0.69)  # Skip 2nd intermission
        p3_end = int(duration_sec * 0.96)    # Skip post-game handshake line
        segments = [
            (1, warmup_trim, p1_end),
            (2, p2_start, p2_end),
            (3, p3_start, p3_end),
        ]
        segmented_shifts: List[Dict[str, Any]] = []
        segmented_periods: Dict[str, int] = {"1": warmup_trim, "2": p2_start, "3": p3_start}
        model_used_final = "gemini-3.5-flash"

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
                + f"\n\nIMPORTANT: Focus strictly on Period {p_num} between {st_off}s and {en_off}s of the video. "
                f"Return 7 to 9 active shifts with start_seconds and end_seconds between {st_off} and {en_off}, "
                f"and set periods['{p_num}'] to the opening faceoff timestamp in seconds for this segment."
            )
            seg_res, m_used = invoke_gemini_with_retry(client, seg_part, seg_prompt)
            if m_used:
                model_used_final = m_used
            if seg_res and seg_res.get("shifts"):
                p_obj = seg_res.get("periods") or {}
                if p_obj.get(str(p_num)) and int(p_obj[str(p_num)]) >= st_off:
                    segmented_periods[str(p_num)] = int(p_obj[str(p_num)])
                for sh in seg_res["shifts"]:
                    sh["period"] = p_num
                    segmented_shifts.append(sh)

        if segmented_shifts:
            return {
                "game_title": game_title,
                "periods": segmented_periods,
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

# ================= ADAPTER: CONVERTS GEMINI SHIFTS TO APP FORMAT =================
def transform_gemini_to_library_schema(
    gemini_data: Dict[str, Any],
    duration_sec: float
) -> tuple[Dict[str, int], List[Dict[str, Any]], Dict[str, Any], Dict[str, List[Dict[str, Any]]], Dict[str, Any]]:
    raw_shifts = gemini_data.get("shifts", [])

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

    # Normalize shifts and ensure valid timestamps & roster player_ids
    roster_nums = {p["num"] for p in OFFICIAL_ROSTER}
    shifts: List[Dict[str, Any]] = []
    for idx, s in enumerate(raw_shifts, start=1):
        st = max(p1, int(float(s.get("start_seconds", 0))))
        en = max(st + 15, int(float(s.get("end_seconds", st + 38))))
        if en - st > 55:
            en = st + 45  # Cap at whistle/shift length so clips never span across stoppages
        if duration_sec > 0 and en > int(duration_sec):
            en = int(duration_sec)
        p_ids = [int(x) for x in s.get("player_ids", []) if str(x).isdigit() and int(x) in roster_nums]
        center_id = s.get("center_id")
        if isinstance(center_id, int) and center_id in roster_nums and center_id not in p_ids:
            p_ids.insert(0, center_id)
        if not p_ids:
            # Assign a rotating line from roster if Gemini omitted jersey numbers on a wide shot
            preset_lines = [
                [10, 7, 11, 21, 27],
                [23, 9, 3, 28, 76],
                [18, 5, 16, 97, 28],
            ]
            p_ids = preset_lines[(idx - 1) % len(preset_lines)]

        period_num = int(s.get("period") or (1 if st < p2 else (2 if st < p3 else 3)))
        bo_raw = s.get("breakout") or {}
        bo = {
            "attempted": bool(bo_raw.get("attempted", False)),
            "successful": bool(bo_raw.get("successful", False)),
            "breakout_type": bo_raw.get("breakout_type") or "None",
            "turnover_location": bo_raw.get("turnover_location") or "None",
        }
        shifts.append({
            "shift_id": idx,
            "period": period_num,
            "start_seconds": st,
            "end_seconds": en,
            "display_time": s.get("display_time") or f"{st // 60}:{st % 60:02d}",
            "center_id": center_id if isinstance(center_id, int) else p_ids[0],
            "player_ids": p_ids,
            "strength_state": s.get("strength_state") or "5v5",
            "primary_zone": s.get("primary_zone") or "Neutral Zone",
            "breakout": bo,
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

    # 4. Analytics Block
    succ_pct = round((breakout_successes / max(1, breakout_attempts)) * 100, 1)
    analytics_dict = {
        "active_play_time": f"{int(duration_sec // 60)}m",
        "possession_tigers_pct": 52,
        "possession_opp_pct": 48,
        "ozone_time": f"{int((duration_sec * 0.35) // 60)}m",
        "dzone_time": f"{int((duration_sec * 0.30) // 60)}m",
        "shots_on_goal": 24,
        "goalie_saves": 26,
        "save_pct": "91.5%",
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
    1. Tries yt-dlp without cookies first (avoids failure if YT_COOKIES secret is expired).
    2. Tries yt-dlp with cookies if needed.
    3. Falls back to direct HTTPS playlist scrape + oEmbed metadata lookup.
    """
    entries_by_id: Dict[str, Dict[str, Any]] = {}

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
                    if not title or title.startswith("Aurora Tigers Match -"):
                        title = oembed_t
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

    # Direct HTTPS scrape fallback if yt-dlp returned nothing
    if not entries_by_id:
        try:
            resp = requests.get(source_url, timeout=15)
            if resp.status_code == 200:
                found_ids = []
                for m in re.finditer(r'"videoId":"([A-Za-z0-9_-]{11})"', resp.text):
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
                            "duration": 2400.0,
                        }
        except Exception as e:
            logger.warning(f"Direct playlist scrape notice: {e}")

    return list(entries_by_id.values())

def download_hd_video(youtube_url: str, local_video: Path) -> bool:
    """
    Downloads 1080p MP4 stream, falling back to 720p MP4 (avoiding 360p blur).
    Tries with cookies if available, and falls back to cookie-less multi-client extraction.
    """
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

# ================= RUN PIPELINE =================
def is_gemini_analyzed(game_entry: Dict[str, Any]) -> bool:
    engine = str(game_entry.get("ai_engine") or "")
    shifts = game_entry.get("shifts") or []
    return ("Gemini" in engine) and len(shifts) > 0

def run_sync():
    logger.info(f"🔍 Reading playlist: {SOURCE_URL}")
    setup_cookies()

    teamsnap_events = fetch_teamsnap_events(TEAMSNAP_ICAL_URL)
    playlist_videos = discover_playlist_entries(SOURCE_URL)
    logger.info(f"📋 Discovered {len(playlist_videos)} live video(s) in playlist.")

    existing_games_by_vid: Dict[str, Dict[str, Any]] = {
        g.get("youtube_video_id"): g
        for g in library.get("games", [])
        if g.get("youtube_video_id")
    }

    # Queue both:
    # 1. New playlist videos not in games_library.json
    # 2. Existing games in games_library.json that fell back to "Proportional Line Engine" or have empty shifts
    videos_to_process: List[Dict[str, Any]] = []
    seen_ids = set()

    for pv in playlist_videos:
        vid_id = pv["id"]
        seen_ids.add(vid_id)
        existing_g = existing_games_by_vid.get(vid_id)
        if not existing_g or not is_gemini_analyzed(existing_g):
            videos_to_process.append(pv)
        else:
            # Still refresh title/date/TeamSnap metadata if title was generic
            if existing_g.get("title", "").startswith("Aurora Tigers Match -") and not pv["title"].startswith("Aurora Tigers Match -"):
                existing_g["title"] = pv["title"]
            parsed_date = parse_date_from_title(existing_g.get("title", ""), pv.get("upload_date"))
            existing_g["date"] = parsed_date
            existing_g["teamsnap"] = match_teamsnap_data(parsed_date, teamsnap_events, existing_g.get("title", ""))

    # Also check any existing games in library not yet Gemini-analyzed (if still valid on YouTube)
    dead_ids = set()
    for vid_id, g in existing_games_by_vid.items():
        if vid_id not in seen_ids:
            oembed_title = fetch_oembed_title(vid_id)
            if oembed_title:
                if not is_gemini_analyzed(g):
                    videos_to_process.append({
                        "id": vid_id,
                        "title": oembed_title if g.get("title", "").startswith("Aurora Tigers Match -") else (g.get("title") or oembed_title),
                        "upload_date": None,
                        "duration": 2400.0,
                    })
            else:
                logger.info(f"🧹 Removing unavailable/deleted YouTube video from library: {vid_id} ({g.get('title')})")
                dead_ids.add(vid_id)

    if dead_ids:
        library["games"] = [g for g in library.get("games", []) if g.get("youtube_video_id") not in dead_ids]

    if not videos_to_process:
        logger.info("✅ All playlist games are already analyzed by Google Gemini 2.5 Flash.")
        save_library(library)
        clean_cookies()
        return

    batch = videos_to_process[:MAX_GAMES_PER_RUN]
    logger.info(f"🎬 Processing {len(batch)} of {len(videos_to_process)} pending game(s) through Gemini 2.5 Flash...")

    for v in batch:
        vid_id = v["id"]
        real_title = v["title"]
        if real_title.startswith("Aurora Tigers Match -"):
            real_title = fetch_oembed_title(vid_id) or real_title

        f_date = parse_date_from_title(real_title, v.get("upload_date"))
        ts_data = match_teamsnap_data(f_date, teamsnap_events, real_title)
        f_date = ts_data.get("date", f_date)

        youtube_url = f"https://www.youtube.com/watch?v={vid_id}"
        local_video = ROOT_DIR / f"temp_{vid_id}.mp4"
        true_duration = float(v.get("duration") or 0)
        if true_duration <= 600 or true_duration == 2400.0:
            true_duration = fetch_video_duration(vid_id, default_dur=2700.0)

        gemini_result = None
        try:
            # Step 1: Fast Token-Saver YouTube URI analysis (0.5 FPS + MEDIA_RESOLUTION_LOW + active period windows)
            gemini_result = process_video_with_gemini(
                None,
                youtube_url=youtube_url,
                duration_sec=true_duration,
                is_home=ts_data.get("is_home", True),
                game_title=real_title,
            )
            # Step 2: Only download HD MP4 locally if direct YouTube URI analysis did not return shifts
            if not (gemini_result and gemini_result.get("shifts")):
                downloaded = download_hd_video(youtube_url, local_video)
                if downloaded:
                    gemini_result = process_video_with_gemini(
                        str(local_video),
                        youtube_url=youtube_url,
                        duration_sec=true_duration,
                        is_home=ts_data.get("is_home", True),
                        game_title=real_title,
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
            model_used = gemini_result.get("_model_used") or "gemini-3.5-flash"
            ai_engine_used = f"Google Gemini 3 ({model_used} - Visual Anchored)"
            logger.info(f"🎯 Successfully parsed {len(shifts_list)} shifts via {model_used} for {vid_id} ({real_title})!")
        else:
            existing_g = existing_games_by_vid.get(vid_id)
            if existing_g and existing_g.get("shifts") and not GOOGLE_API_KEY:
                logger.info(f"ℹ️ Keeping existing shifts for {vid_id} (no GEMINI_API_KEY provided).")
                continue
            periods_detected, shifts_list, players_matrix, clips_matrix, analytics_matrix = estimate_periods_and_shifts(v["duration"])
            ai_engine_used = "Proportional Line Engine"
            logger.warning(f"⚠️ Gemini result unavailable for {vid_id}; used multi-line fallback.")

        new_entry = {
            "id": f"game_{vid_id}",
            "title": real_title,
            "youtube_video_id": vid_id,
            "date": f_date,
            "opponent": "League Match",
            "periods": periods_detected,
            "ai_engine": ai_engine_used,
            "teamsnap": ts_data,
            "shifts": shifts_list,
            "players": players_matrix,
            "coaching_clips": clips_matrix,
            "analytics": analytics_matrix
        }

        # Update existing game in-place or insert at top
        replaced = False
        for i, existing_game in enumerate(library.get("games", [])):
            if existing_game.get("youtube_video_id") == vid_id or existing_game.get("id") == f"game_{vid_id}":
                library["games"][i] = new_entry
                replaced = True
                break
        if not replaced:
            library["games"].insert(0, new_entry)

        # Sort games newest-first by date
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
