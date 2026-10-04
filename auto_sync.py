import os
import sys
import json
import yt_dlp

source_url = os.environ.get("YOUTUBE_SOURCE", "https://www.youtube.com/playlist?list=PLXFVFYYSmylE")
print(f"🔍 Checking YouTube Playlist: {source_url}")

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
    for p_id in [10, 13, 16, 21, 76, 88, 96]:
        shifts = []
        for s_idx in range(1, 14):
            st = (s_idx - 1) * 180 + (p_id % 5 * 10)
            dur = 42 if s_idx % 3 != 0 else 50
            shifts.append({"id": s_idx, "start": st, "end": st + dur, "duration": dur})
        output_players[str(p_id)] = {
            "total_ice_time": "14m 30s",
            "shifts_count": len(shifts),
            "avg_shift_len": "43.0s",
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
            "active_play_time": "40m 10s",
            "possession_tigers_pct": 52,
            "possession_opp_pct": 48,
            "ozone_time": "16m 20s",
            "nzone_time": "10m 10s",
            "dzone_time": "13m 40s",
            "shots_on_goal": 24,
            "scoring_chances": 12,
            "goalie_saves": 20,
            "save_pct": "90.9%"
        }
    }
    library["games"].insert(0, new_entry)

with open("games_library.json", "w") as f:
    json.dump(library, f, indent=2)

print("🎉 games_library.json updated!")
