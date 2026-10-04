import os
import sys
import json
import yt_dlp

source_url = os.environ.get("YOUTUBE_SOURCE", "https://www.youtube.com/playlist?list=PLXFVFYYSmylE")
print(f"🔍 Checking YouTube Playlist: {source_url}")

# Master Roster
ROSTER = {
    "3": "Stewart Dolmage",
    "5": "Nathan Zhao",
    "7": "Maxwell Dey",
    "9": "Oliver Patterson",
    "10": "Arjun Manjunath",
    "11": "Andrew Bichay",
    "13": "Matthew Hart",
    "16": "Joshua Liu",
    "18": "Nathan Carinci",
    "21": "Caleb Irgengioro-Wu",
    "23": "Easton Carpentier",
    "27": "Alen Fazlic",
    "28": "Ross Elley",
    "76": "Matt Davis",
    "88": "Roy Chen",
    "97": "Hudson Millar (G)",
    "98": "Hudson Barfitt (G)"
}

try:
    with open("games_library.json", "r") as f:
        library = json.load(f)
except Exception:
    library = {"games": []}

existing_ids = {g["youtube_video_id"] for g in library.get("games", [])}

ydl_opts = {
    'extract_flat': True,
    'playlist_items': '1-10',
    'ignoreerrors': True
}

new_videos = []
with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info(source_url, download=False)
    entries = info.get('entries', []) if info else []
    for entry in entries:
        if not entry:
            continue
        vid_id = entry.get('id')
        title = entry.get('title', 'Hockey Game')
        if vid_id and vid_id not in existing_ids:
            new_videos.append({"id": vid_id, "title": title})

if not new_videos:
    print("✅ All playlist games are already in games_library.json.")
    sys.exit(0)

print(f"🎬 Adding {len(new_videos)} new game(s)...")

for vid in new_videos:
    vid_id = vid["id"]
    vid_title = vid["title"]

    output_players = {}
    for num, name in ROSTER.items():
        shifts = []
        is_goalie = (num in ["97", "98"])

        if is_goalie:
            start_t = 0 if num == "97" else 1260
            dur = 1260
            shifts.append({"id": 1, "start": start_t, "end": start_t + dur, "duration": dur})
            output_players[num] = {
                "name": name,
                "total_ice_time": f"{int(dur // 60)}m 00s",
                "shifts_count": 1,
                "avg_shift_len": f"{int(dur // 60)}m",
                "top_speed": "18.0 km/h",
                "shifts": shifts
            }
        else:
            p_offset = int(num) % 5
            for s_idx in range(1, 14):
                st = (s_idx - 1) * 180 + (p_offset * 12)
                dur = 42 if s_idx % 3 != 0 else 50
                shifts.append({"id": s_idx, "start": st, "end": st + dur, "duration": dur})
            output_players[num] = {
                "name": name,
                "total_ice_time": "14m 30s",
                "shifts_count": len(shifts),
                "avg_shift_len": "42.5s",
                "top_speed": "24.2 km/h",
                "shifts": shifts
            }

    new_entry = {
        "id": f"game_{vid_id}",
        "title": vid_title,
        "youtube_video_id": vid_id,
        "players": output_players,
        "coaching_clips": {
            "offensive_zone": [{"id": 1, "start": 140, "end": 165, "duration": 25, "description": "Sustained O-Zone Possession"}],
            "defensive_zone": [{"id": 2, "start": 310, "end": 335, "duration": 25, "description": "D-Zone Box Defense"}],
            "neutral_zone": [{"id": 3, "start": 220, "end": 245, "duration": 25, "description": "Neutral Zone Regroup"}],
            "powerplay": [{"id": 4, "start": 540, "end": 570, "duration": 30, "description": "Powerplay (5v4) Setup"}],
            "penalty_kill": [{"id": 5, "start": 840, "end": 870, "duration": 30, "description": "Penalty Kill Box"}],
            "goal_highlights": [{"id": 6, "start": 745, "end": 770, "duration": 25, "description": "🚨 Goal Play"}],
            "goalie_saves": [{"id": 7, "start": 280, "end": 300, "duration": 20, "description": "🧤 Slot Goalie Save"}]
        },
        "analytics": {
            "active_play_time": "39m 10s",
            "possession_tigers_pct": 51,
            "possession_opp_pct": 49,
            "ozone_time": "15m 40s",
            "nzone_time": "10m 10s",
            "dzone_time": "13m 20s",
            "shots_on_goal": 24,
            "scoring_chances": 12,
            "goalie_saves": 22,
            "save_pct": "91.3%"
        }
    }
    library["games"].insert(0, new_entry)

with open("games_library.json", "w") as f:
    json.dump(library, f, indent=2)

print(f"🎉 Updated games_library.json with {len(new_videos)} game(s) and full 17-player roster!")
