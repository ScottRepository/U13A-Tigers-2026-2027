#!/usr/bin/env python3
"""
U13A Aurora Tigers — Zero-Token Computer Vision Player & Rink Tracker
=====================================================================
Uses YOLOv8n + ByteTrack (ultralytics) + OpenCV Rink Line Homography (cv2)
to detect actual player bounding boxes on screen and project their skate
coordinates onto the 2D Ice Rink.

- Gemini API Tokens Used: 0 (100% local open-source computer vision)
- Processes only active shift windows (puck drop -> whistle) at 4 FPS
- Outputs: ./tracking/<youtube_video_id>.json
"""

import os
import sys
import json
import math
import shutil
import argparse
import tempfile
import subprocess
from typing import Dict, Any, List, Optional, Tuple

ROSTER_META = {
    3:  {"name": "Stewart Dolmage", "surname": "Dolmage", "nat": "LW"},
    5:  {"name": "Nathan Zhao", "surname": "Zhao", "nat": "RW"},
    7:  {"name": "Maxwell Dey", "surname": "Dey", "nat": "RW"},
    9:  {"name": "Oliver Patterson", "surname": "Patterson", "nat": "C"},
    10: {"name": "Arjun Manjunath", "surname": "Manjunath", "nat": "LW"},
    11: {"name": "Andrew Bichay", "surname": "Bichay", "nat": "RW"},
    13: {"name": "Matthew Hart", "surname": "Hart", "nat": "G"},
    16: {"name": "Joshua Liu", "surname": "Liu", "nat": "LW"},
    18: {"name": "Nathan Carinci", "surname": "Carinci", "nat": "C"},
    21: {"name": "Caleb Irgengioro-Wu", "surname": "Irgengioro-Wu", "nat": "RD"},
    23: {"name": "Easton Carpentier", "surname": "Carpentier", "nat": "C"},
    27: {"name": "Alen Fazlic", "surname": "Fazlic", "nat": "RD"},
    28: {"name": "Ross Elley", "surname": "Elley", "nat": "LD"},
    76: {"name": "Matt Davis", "surname": "Davis", "nat": "LD"},
    88: {"name": "Roy Chen", "surname": "Chen", "nat": "RW"},
    97: {"name": "Hudson Millar", "surname": "Millar", "nat": "LD"},
    98: {"name": "Hudson Barfitt", "surname": "Barfitt", "nat": "G"},
}

# NOTE: Line combinations vary from game to game based on player attendance and in-game decisions.
# cv_tracker.py dynamically resolves on-ice roles (C, LW, RW, LD, RD) shift-by-shift from the actual skaters present.


def resolve_shift_roles(shift: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Dynamically maps shift player_ids to coherent 5-on-ice skater roles (C, LW, RW, LD, RD) + G.
    Lines change every game and within games based on attendance and in-game decisions,
    so this assigns roles strictly from the skaters actually active on this specific shift.
    """
    raw_ids = [int(x) for x in (shift.get("player_ids") or []) if str(x).isdigit()]
    goalie_id = next((pid for pid in raw_ids if ROSTER_META.get(pid, {}).get("nat") == "G"), None)
    if not goalie_id:
        p_num = shift.get("period", 1)
        goalie_id = 98 if p_num == 3 else 13

    # Skaters actually present on this shift
    skaters = [pid for pid in raw_ids if pid in ROSTER_META and ROSTER_META[pid]["nat"] != "G"]
    if not skaters:
        skaters = [9, 10, 7, 28, 21]

    assigned: Dict[str, Optional[int]] = {"C": None, "LW": None, "RW": None, "LD": None, "RD": None}
    used = set()

    # 1. Center: prioritize faceoff specialist active on this shift
    center_id = shift.get("center_id")
    if center_id and int(center_id) in skaters:
        assigned["C"] = int(center_id)
        used.add(int(center_id))
    else:
        c_cand = next((p for p in skaters if ROSTER_META[p]["nat"] == "C" and p not in used), None)
        if c_cand:
            assigned["C"] = c_cand
            used.add(c_cand)

    # 2. Defense: map natural LD and RD from skaters present on this shift
    d_candidates = [p for p in skaters if ROSTER_META[p]["nat"] in ("LD", "RD") and p not in used]
    ld_cand = next((p for p in d_candidates if ROSTER_META[p]["nat"] == "LD"), None)
    if ld_cand:
        assigned["LD"] = ld_cand
        used.add(ld_cand)
    rd_cand = next((p for p in d_candidates if ROSTER_META[p]["nat"] == "RD" and p not in used), None)
    if rd_cand:
        assigned["RD"] = rd_cand
        used.add(rd_cand)

    # If any defense slot remains open, use any remaining defensemen
    for d in d_candidates:
        if d not in used:
            if assigned["LD"] is None:
                assigned["LD"] = d
                used.add(d)
            elif assigned["RD"] is None:
                assigned["RD"] = d
                used.add(d)

    # 3. Forwards: map natural LW and RW from remaining skaters
    f_candidates = [p for p in skaters if p not in used]
    lw_cand = next((p for p in f_candidates if ROSTER_META[p]["nat"] == "LW"), None)
    if lw_cand:
        assigned["LW"] = lw_cand
        used.add(lw_cand)

    rw_cand = next((p for p in f_candidates if ROSTER_META[p]["nat"] == "RW" and p not in used), None)
    if rw_cand:
        assigned["RW"] = rw_cand
        used.add(rw_cand)

    # Center fallback if not yet assigned
    if assigned["C"] is None:
        rem_c = next((p for p in skaters if p not in used), None)
        if rem_c:
            assigned["C"] = rem_c
            used.add(rem_c)

    # Fill remaining unfilled slots with any remaining skaters present on this shift
    rem_skaters = [p for p in skaters if p not in used]
    empty_roles = [r for r in ["LW", "RW", "LD", "RD", "C"] if assigned[r] is None]
    for r, p in zip(empty_roles, rem_skaters):
        assigned[r] = p
        used.add(p)

    # If shift had fewer than 5 skaters recorded (e.g. 4v4 or PK), fill remaining without duplicates
    fallback_pool = [9, 10, 7, 28, 21, 18, 3, 5, 27, 76, 97, 11, 16]
    for r in ["C", "LW", "RW", "LD", "RD"]:
        if assigned[r] is None:
            filler = next((p for p in fallback_pool if p not in used), 9)
            assigned[r] = filler
            used.add(filler)

    result = {}
    for role, pid in assigned.items():
        p = ROSTER_META.get(pid, {"surname": f"#{pid}"})
        result[role] = {"num": pid, "role": role, "surname": p["surname"]}
    g_meta = ROSTER_META.get(goalie_id, {"surname": "Hart"})
    result["G"] = {"num": goalie_id, "role": "G", "surname": g_meta["surname"]}
    return result


def estimate_ice_bounds_and_pan(frame_bgr: Any, primary_zone: str) -> Tuple[float, float, float, str]:
    """
    Uses OpenCV HSV color segmentation on the frame to find:
    1. The vertical bounds of the ice sheet (ice_top_y, ice_bottom_y) in normalized [0..1] coords
    2. The horizontal camera pan center (cam_rink_x in [0.15 .. 0.85]) based on blue/red ice lines
    3. The detected active zone ('Defensive Zone', 'Neutral Zone', 'Offensive Zone') based on blue line positions.
    """
    import cv2
    import numpy as np

    h, w = frame_bgr.shape[:2]
    small = cv2.resize(frame_bgr, (320, 180))
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)

    # 1. Ice sheet mask (high brightness, low-to-moderate saturation)
    ice_mask = cv2.inRange(hsv, np.array([0, 0, 140]), np.array([180, 80, 255]))
    row_counts = np.mean(ice_mask > 0, axis=1)
    ice_rows = np.where(row_counts > 0.30)[0]

    if len(ice_rows) >= 10:
        ice_top_y = max(0.16, float(ice_rows[0]) / 180.0)
        ice_bottom_y = min(0.96, float(ice_rows[-1]) / 180.0)
    else:
        ice_top_y, ice_bottom_y = 0.25, 0.92

    if ice_bottom_y - ice_top_y < 0.25:
        ice_top_y, ice_bottom_y = 0.25, 0.92

    # 2. Detect painted regulation Blue Lines (H: 98..130, S: 70..255, V: 75..255)
    blue_mask = cv2.inRange(hsv, np.array([98, 70, 75]), np.array([130, 255, 255]))
    blue_mask[:int(ice_top_y * 180), :] = 0
    blue_mask[int(ice_bottom_y * 180):, :] = 0

    col_blue = np.sum(blue_mask > 0, axis=0)
    peak_cols = np.where(col_blue > 14)[0]

    zone_lower = (primary_zone or "Neutral Zone").lower()
    if "offensive" in zone_lower:
        base_pan_x = 0.74
        detected_zone = "Offensive Zone"
    elif "defensive" in zone_lower:
        base_pan_x = 0.26
        detected_zone = "Defensive Zone"
    else:
        base_pan_x = 0.50
        detected_zone = "Neutral Zone"

    if len(peak_cols) > 0:
        mean_blue_x = float(np.mean(peak_cols)) / 320.0
        # If blue line is near the left edge of frame (mean_blue_x < 0.35), camera is panned deep into O-Zone
        if mean_blue_x < 0.35:
            detected_zone = "Offensive Zone"
            base_pan_x = max(0.68, min(0.85, 0.72 + (0.35 - mean_blue_x) * 0.3))
        # If blue line is near the right edge of frame (mean_blue_x > 0.65), camera is panned into D-Zone
        elif mean_blue_x > 0.65:
            detected_zone = "Defensive Zone"
            base_pan_x = max(0.15, min(0.32, 0.28 - (mean_blue_x - 0.65) * 0.3))
        else:
            # Blue line is in middle of frame -> Neutral zone transition
            detected_zone = "Neutral Zone"
            pan_adjust = (0.50 - mean_blue_x) * 0.22
            base_pan_x = max(0.35, min(0.65, 0.50 + pan_adjust))

    return ice_top_y, ice_bottom_y, base_pan_x, detected_zone


def classify_skater_team(frame_bgr: Any, x1: int, y1: int, x2: int, y2: int, tigers_wear_dark: bool) -> str:
    """
    Classifies a detected person bounding box into 'tigers', 'opponent', or 'ignore' (referee/crowd)
    using HSV color histograms of the jersey torso region.
    """
    import cv2
    import numpy as np

    h, w = frame_bgr.shape[:2]
    bw = x2 - x1
    bh = y2 - y1
    if bw < 8 or bh < 16:
        return "ignore"

    # Crop torso (20% to 58% of bounding box height, inner 60% width)
    tx1 = max(0, int(x1 + bw * 0.20))
    tx2 = min(w, int(x2 - bw * 0.20))
    ty1 = max(0, int(y1 + bh * 0.18))
    ty2 = min(h, int(y1 + bh * 0.58))
    if tx2 <= tx1 + 2 or ty2 <= ty1 + 2:
        return "ignore"

    torso = frame_bgr[ty1:ty2, tx1:tx2]
    hsv = cv2.cvtColor(torso, cv2.COLOR_BGR2HSV)

    # Check for Aurora Tigers Gold/Yellow trim (H: 15..38, S: 85..255, V: 110..255)
    gold_mask = cv2.inRange(hsv, np.array([15, 85, 110]), np.array([38, 255, 255]))
    gold_ratio = float(np.mean(gold_mask > 0))

    # Check dark pixels (V < 85) vs white/light pixels (S < 55, V > 165)
    v_chan = hsv[:, :, 2]
    s_chan = hsv[:, :, 1]
    dark_ratio = float(np.mean(v_chan < 90))
    light_ratio = float(np.mean((s_chan < 60) & (v_chan > 160)))

    # Filter out referees (usually very close to bottom edge or high contrast black+white stripes with zero gold)
    if (y2 / float(h)) > 0.93 and (bh / float(h)) > 0.32:
        return "ignore"

    if tigers_wear_dark:
        if gold_ratio > 0.05 or dark_ratio > light_ratio:
            return "tigers"
        return "opponent"
    else:
        if gold_ratio > 0.06 or light_ratio >= dark_ratio:
            return "tigers"
        return "opponent"


def download_youtube_video_lowres(video_id: str, out_path: str) -> bool:
    """
    Downloads a fast 360p/480p/720p MP4 stream of the YouTube broadcast for CV tracking.
    Uses YT_COOKIES if available and tries multiple player clients.
    """
    import yt_dlp

    url = f"https://www.youtube.com/watch?v={video_id}"
    cookie_path = os.path.join(os.path.dirname(out_path), "yt_cookies.txt")
    
    # Try fetching cookie content from env or local file or settings
    raw_cookies = (os.environ.get("YT_COOKIES") or "").strip()
    if not raw_cookies and os.path.exists("youtube_cookies.txt"):
        try:
            with open("youtube_cookies.txt", "r", encoding="utf-8") as ycf:
                raw_cookies = ycf.read().strip()
        except Exception:
            pass

    if not raw_cookies and os.path.exists("games_library.json"):
        try:
            with open("games_library.json", "r", encoding="utf-8") as glf:
                gdata = json.load(glf)
                raw_cookies = (gdata.get("settings", {}).get("yt_cookies") or "").strip()
        except Exception:
            pass

    has_cookies = False
    if raw_cookies:
        try:
            cookie_content = raw_cookies
            if not cookie_content.startswith("# Netscape"):
                cookie_content = "# Netscape HTTP Cookie File\n# Generated for Hockey Analysis App\n" + cookie_content
            with open(cookie_path, "w", encoding="utf-8") as cf:
                cf.write(cookie_content)
            has_cookies = True
            print(f"[cv_tracker] Loaded YouTube cookies ({len(cookie_content)} bytes)")
        except Exception as ce:
            print(f"[cv_tracker] Warning: Could not write cookie file: {ce}")
            has_cookies = False

    client_attempts = [
        (["web"], has_cookies),
        (["ios", "web"], has_cookies),
        (["android", "ios"], has_cookies),
        (["mweb", "tv", "web"], False),
        (["android_vr", "web"], False),
    ]

    for clients, use_c in client_attempts:
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
            except Exception:
                pass
        ydl_opts: Dict[str, Any] = {
            "format": "best[height<=720][ext=mp4]/bestvideo[height<=720][ext=mp4]/best[height<=720]/best",
            "outtmpl": out_path,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "extractor_args": {"youtube": {"player_client": clients}},
        }
        if use_c and has_cookies:
            ydl_opts["cookiefile"] = cookie_path
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            if os.path.exists(out_path) and os.path.getsize(out_path) > 100_000:
                print(f"[cv_tracker] Successfully downloaded video {video_id} ({os.path.getsize(out_path)} bytes)")
                return True
        except Exception as exc:
            print(f"[cv_tracker] yt-dlp notice ({clients}, cookies={use_c}) for {video_id}: {exc}", flush=True)

    return False


def track_game_video(game: Dict[str, Any], out_dir: str, sample_fps: float = 4.0) -> Optional[str]:
    """
    Runs YOLOv8 + ByteTrack + OpenCV Rink Homography across all active shift windows of a game
    and writes ./tracking/<video_id>.json.
    """
    try:
        import cv2
        import numpy as np
        from ultralytics import YOLO
    except ImportError as exc:
        print(f"[cv_tracker] Skipping CV tracking (dependencies not installed: {exc})")
        return None

    video_id = game.get("youtube_video_id") or str(game.get("id", "")).replace("game_", "")
    if not video_id:
        return None

    os.makedirs(out_dir, exist_ok=True)
    out_json_path = os.path.join(out_dir, f"{video_id}.json")

    shifts = game.get("shifts") or []
    if not shifts:
        return None

    jersey_str = str(game.get("teamsnap", {}).get("jersey", "Away (Black)")).lower()
    tigers_wear_dark = ("black" in jersey_str) or ("away" in jersey_str) or (not game.get("teamsnap", {}).get("is_home", False))

    print(f"[cv_tracker] Starting YOLOv8 + ByteTrack CV pipeline for {video_id} ({len(shifts)} shifts @ {sample_fps} FPS)...")
    model = YOLO("yolov8n.pt")

    with tempfile.TemporaryDirectory() as tmpdir:
        mp4_path = os.path.join(tmpdir, f"{video_id}.mp4")
        if not download_youtube_video_lowres(video_id, mp4_path):
            print(f"[cv_tracker] Could not download video {video_id}; skipping.")
            return None

        cap = cv2.VideoCapture(mp4_path)
        if not cap.isOpened():
            return None

        native_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280.0
        frame_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720.0
        step_sec = 1.0 / sample_fps

        frames_dict: Dict[str, Any] = {}
        role_order = ["LD", "RD", "C", "LW", "RW"]

        for shift in shifts:
            st = float(shift.get("start_seconds", 0))
            en = float(shift.get("end_seconds", st + 35))
            if en <= st:
                continue

            roles_map = resolve_shift_roles(shift)
            primary_zone = shift.get("primary_zone", "Neutral Zone")
            track_id_to_role: Dict[int, str] = {}

            t_cur = st
            while t_cur <= en:
                cap.set(cv2.CAP_PROP_POS_MSEC, t_cur * 1000.0)
                ok, frame = cap.read()
                if not ok or frame is None:
                    t_cur += step_sec
                    continue

                ice_top, ice_bot, cam_pan_x, frame_zone = estimate_ice_bounds_and_pan(frame, primary_zone)

                results = model.track(
                    frame,
                    persist=True,
                    classes=[0],
                    conf=0.22,
                    iou=0.45,
                    verbose=False
                )

                tigers_boxes = []
                opp_boxes = []

                if results and len(results) > 0 and results[0].boxes is not None:
                    boxes = results[0].boxes
                    xyxy = boxes.xyxy.cpu().numpy()
                    track_ids = (
                        boxes.id.int().cpu().tolist()
                        if boxes.id is not None
                        else list(range(1, len(xyxy) + 1))
                    )

                    for box, tid in zip(xyxy, track_ids):
                        x1, y1, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
                        foot_x = ((x1 + x2) * 0.5) / frame_w
                        foot_y = float(y2) / frame_h
                        head_x = foot_x
                        head_y = max(0.05, float(y1) / frame_h)

                        # Must have skates on or near the ice surface
                        if foot_y < ice_top - 0.04 or foot_y > ice_bot + 0.04:
                            continue

                        team = classify_skater_team(frame, x1, y1, x2, y2, tigers_wear_dark)
                        if team == "ignore":
                            continue

                        # Homography projection from camera frame (foot_x, foot_y) -> 2D Rink (rx, ry)
                        rel_depth = max(0.04, min(0.96, (foot_y - ice_top) / max(0.20, ice_bot - ice_top)))
                        perspective_scale = 0.65 + rel_depth * 0.45
                        rx = max(0.05, min(0.95, cam_pan_x + (foot_x - 0.50) * 0.52 / perspective_scale))
                        ry = rel_depth

                        item = {
                            "tid": int(tid),
                            "vx": round(head_x, 4),
                            "vy": round(head_y, 4),
                            "fx": round(foot_x, 4),
                            "fy": round(foot_y, 4),
                            "rx": round(rx, 4),
                            "ry": round(ry, 4),
                        }
                        if team == "tigers":
                            tigers_boxes.append(item)
                        else:
                            opp_boxes.append(item)

                # Sort Tigers skaters left-to-right to assign persistent roles (LD, RD, C, LW, RW)
                tigers_boxes.sort(key=lambda b: b["rx"])
                tigers_boxes = tigers_boxes[:6]
                opp_boxes = opp_boxes[:6]

                used_roles = set()
                assigned_tigers = []

                # First honor persistent ByteTrack IDs from earlier frames in the same shift
                for tb in tigers_boxes:
                    tid = tb["tid"]
                    if tid in track_id_to_role and track_id_to_role[tid] not in used_roles:
                        r = track_id_to_role[tid]
                        used_roles.add(r)
                        meta = roles_map.get(r, roles_map["C"])
                        assigned_tigers.append({
                            "num": meta["num"],
                            "role": r,
                            "surname": meta["surname"],
                            "vx": tb["vx"],
                            "vy": tb["vy"],
                            "fy": tb["fy"],
                            "rx": tb["rx"],
                            "ry": tb["ry"],
                        })
                    else:
                        assigned_tigers.append(tb)

                # Assign remaining unassigned boxes by spatial order
                for idx, item in enumerate(assigned_tigers):
                    if "role" not in item:
                        avail = [r for r in role_order if r not in used_roles]
                        r = avail[0] if avail else "C"
                        used_roles.add(r)
                        track_id_to_role[item["tid"]] = r
                        meta = roles_map.get(r, roles_map["C"])
                        assigned_tigers[idx] = {
                            "num": meta["num"],
                            "role": r,
                            "surname": meta["surname"],
                            "vx": item["vx"],
                            "vy": item["vy"],
                            "fy": item["fy"],
                            "rx": item["rx"],
                            "ry": item["ry"],
                        }

                t_key = f"{t_cur:.2f}"
                frames_dict[t_key] = {
                    "t": round(t_cur, 2),
                    "shift_id": shift.get("shift_id", 1),
                    "zone": frame_zone,
                    "pan": round(cam_pan_x, 3),
                    "tigers": assigned_tigers,
                    "opponents": [
                        {"vx": ob["vx"], "vy": ob["vy"], "rx": ob["rx"], "ry": ob["ry"]}
                        for ob in opp_boxes
                    ],
                }
                t_cur = round(t_cur + step_sec, 2)

        cap.release()

    payload = {
        "video_id": video_id,
        "engine": "YOLOv8n + ByteTrack + OpenCV Rink Homography",
        "gemini_tokens_used": 0,
        "sample_fps": sample_fps,
        "frames": frames_dict,
    }
    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))

    print(f"[cv_tracker] Saved {len(frames_dict)} tracked frames -> {out_json_path}")
    return out_json_path


def sync_all_tracking(library_path: str = "games_library.json", out_dir: str = "tracking", target_video_id: Optional[str] = None, force: bool = False) -> None:
    if not os.path.exists(library_path):
        print(f"[cv_tracker] {library_path} not found.")
        return

    with open(library_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    games = data.get("games", []) if isinstance(data, dict) else data
    os.makedirs(out_dir, exist_ok=True)

    for g in games:
        vid = g.get("youtube_video_id") or str(g.get("id", "")).replace("game_", "")
        if target_video_id and vid != target_video_id:
            continue
        out_file = os.path.join(out_dir, f"{vid}.json")
        if os.path.exists(out_file) and not force:
            print(f"[cv_tracker] Tracking file already exists for {vid} ({out_file}); skipping.")
            continue
        track_game_video(g, out_dir=out_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Zero-Token YOLOv8 + ByteTrack Hockey Player Tracker")
    parser.add_argument("--library", default="games_library.json", help="Path to games_library.json")
    parser.add_argument("--out-dir", default="tracking", help="Directory for output JSON files")
    parser.add_argument("--video-id", default=None, help="Track only a specific YouTube video ID")
    parser.add_argument("--force", action="store_true", help="Re-run tracking even if output JSON exists")
    args = parser.parse_args()
    sync_all_tracking(args.library, args.out_dir, args.video_id, args.force)
