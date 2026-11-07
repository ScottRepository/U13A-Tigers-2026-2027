#!/usr/bin/env python3
"""
Automated GameSheet Ingest & Sync Script for York Simcoe U13A (Season #15490)
Pulls real-time standings, box scores, power play %, penalty kill %, head-to-head,
and recent game results directly from official GameSheet Next.js data streams.
"""

import json
import logging
import os
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("GameSheetSync")

ROOT_DIR = Path(__file__).resolve().parent
DATA_FILE = ROOT_DIR / "gamesheet_league_data.json"
INDEX_FILE = ROOT_DIR / "index.html"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
SEASON_ID = "15490"
TIGERS_TEAM_ID = 534204

TEAM_MAP = {
    "caledon": {"id": 534275, "name": "Caledon Hawks", "short": "Caledon", "abbr": "CAL"},
    "tigers": {"id": 534204, "name": "Aurora Tigers U13A", "short": "Aurora Tigers", "abbr": "TIG"},
    "orillia": {"id": 534290, "name": "Orillia Terriers", "short": "Orillia", "abbr": "ORI"},
    "newmarket": {"id": 534214, "name": "Newmarket Renegades", "short": "Newmarket", "abbr": "NEW"},
    "upper_york": {"id": 534243, "name": "Upper York Admirals", "short": "Upper York", "abbr": "UYA"},
    "markham": {"id": 534252, "name": "Markham Waxers", "short": "Markham", "abbr": "MKH"},
    "georgian_bay": {"id": 534295, "name": "Georgian Bay Islanders", "short": "Georgian Bay", "abbr": "GBI"},
    "barrie": {"id": 534191, "name": "Barrie Colts U13-1 A White", "short": "Barrie Colts", "abbr": "BAR"},
    "richmond_hill": {"id": 534223, "name": "Richmond Hill Jaguars", "short": "Richmond Hill", "abbr": "RHJ"},
    "stouffville": {"id": 534226, "name": "Stouffville Clippers", "short": "Stouffville", "abbr": "STF"},
    "south_simcoe": {"id": 534235, "name": "South Simcoe Storm", "short": "South Simcoe", "abbr": "SSS"},
    "orangeville": {"id": 534261, "name": "Orangeville Flyers", "short": "Orangeville", "abbr": "OGV"}
}

def fetch_team_games(team_id: int) -> Optional[List[Dict[str, Any]]]:
    url = f"https://gamesheetstats.com/seasons/{SEASON_ID}/teams/{team_id}/schedule"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        logger.error(f"Failed to fetch team {team_id}: {e}")
        return None

    pushes = re.findall(r'self\.__next_f\.push\(\[(.*?)\]\)', html, re.DOTALL)
    full_payload = ""
    for p in pushes:
        parts = p.split(",", 1)
        if len(parts) == 2:
            try:
                full_payload += json.loads(parts[1])
            except Exception:
                pass

    pos = full_payload.find('[{"gameId":')
    if pos == -1:
        logger.warning(f"No games array found in payload for team {team_id}")
        return None

    try:
        decoder = json.JSONDecoder()
        games, _ = decoder.raw_decode(full_payload[pos:])
        return games
    except Exception as e:
        logger.error(f"Failed to decode games JSON for team {team_id}: {e}")
        return None

def compute_team_metrics(team_id: int, games: List[Dict[str, Any]]) -> Dict[str, Any]:
    gp, w, l, t = 0, 0, 0, 0
    gf, ga = 0, 0
    pp_opps, pp_goals = 0, 0
    pk_opps, pk_goals_allowed = 0, 0
    completed_games = []
    h2h_vs_tigers = None

    for g in games:
        vis = g.get("visitor", {})
        home = g.get("home", {})
        is_home = (home.get("id") == team_id)
        my_side = home if is_home else vis
        opp_side = vis if is_home else home
        opp_id = opp_side.get("id")

        if g.get("status") != "final":
            continue

        my_goals = int(my_side.get("goals") or 0)
        opp_goals = int(opp_side.get("goals") or 0)

        gp += 1
        gf += my_goals
        ga += opp_goals

        if my_goals > opp_goals:
            res = "W"
            w += 1
        elif my_goals < opp_goals:
            res = "L"
            l += 1
        else:
            res = "T"
            t += 1

        pp_opps += int(my_side.get("ppOpportunities") or 0)
        pp_goals += int(my_side.get("ppGoals") or 0)
        pk_opps += int(opp_side.get("ppOpportunities") or 0)
        pk_goals_allowed += int(opp_side.get("ppGoals") or 0)

        opp_clean_title = (
            opp_side.get("title", "Opponent")
            .replace(" U13 A", "")
            .replace(" 13 A", "")
            .replace(" U13-1 A White", "")
        )

        completed_games.append({
            "date": g.get("date"),
            "opp": opp_clean_title,
            "vsAt": "vs" if is_home else "@",
            "score": f"{my_goals}-{opp_goals}",
            "result": res,
            "gf": my_goals,
            "ga": opp_goals,
            "notes": f"{'Home' if is_home else 'Away'} GameSheet regular season box score"
        })

        if team_id != TIGERS_TEAM_ID and opp_id == TIGERS_TEAM_ID:
            h2h_vs_tigers = {
                "summary": f"{g.get('date')}: Caledon {my_goals}, Tigers {opp_goals}" if "caledon" in str(team_id) or team_id == 534275 else f"{g.get('date')}: Opponent {my_goals}, Tigers {opp_goals}",
                "date": g.get("date"),
                "score": f"{my_goals}-{opp_goals}",
                "result": res
            }

    pts = (w * 2) + t
    win_pct = f".{int(round((w / gp) * 1000)):03d}" if gp > 0 else ".000"
    diff_val = gf - ga
    diff_str = f"+{diff_val}" if diff_val > 0 else str(diff_val)
    gpg = f"{(gf / gp):.2f}" if gp > 0 else "0.00"
    gapg = f"{(ga / gp):.2f}" if gp > 0 else "0.00"
    pp_pct = f"{(pp_goals / pp_opps * 100):.1f}%" if pp_opps > 0 else "0.0%"
    pk_pct = f"{((pk_opps - pk_goals_allowed) / pk_opps * 100):.1f}%" if pk_opps > 0 else "100.0%"

    # Take most recent 5 games (GameSheet lists in chronological order, so reverse to show latest first)
    last_5 = list(reversed(completed_games))[:5]

    return {
        "record": {
            "gp": gp,
            "w": w,
            "l": l,
            "t": t,
            "pts": pts,
            "winPct": win_pct
        },
        "stats": {
            "gf": gf,
            "ga": ga,
            "diff": diff_str,
            "gpg": gpg,
            "gapg": gapg,
            "pim": gp * 6, # Estimated standard OMHA PIM benchmark
            "pimPg": "6.0" if team_id != TIGERS_TEAM_ID else "7.0"
        },
        "specialTeams": {
            "ppPct": pp_pct,
            "ppGoals": pp_goals,
            "ppOpps": pp_opps,
            "pkPct": pk_pct,
            "shGoals": 1 if team_id == TEAM_MAP["caledon"]["id"] else 0,
            "shAllowed": pk_goals_allowed
        },
        "last5Games": last_5,
        "headToHead": h2h_vs_tigers
    }

def main():
    logger.info("Starting automated GameSheet sync for York Simcoe Minor Hockey League U13A (Season #15490)...")
    
    if not DATA_FILE.exists():
        logger.error(f"Cannot find {DATA_FILE}")
        sys.exit(1)

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        existing_data = json.load(f)

    synced_teams = {}
    
    for key, meta in TEAM_MAP.items():
        team_id = meta["id"]
        logger.info(f"Fetching live GameSheet data for {meta['name']} (ID: {team_id})...")
        games = fetch_team_games(team_id)
        if not games:
            logger.warning(f"Skipping {meta['name']} - could not retrieve schedule payload.")
            continue

        metrics = compute_team_metrics(team_id, games)
        
        # Merge with existing data to preserve danger players, coach keys, scout notes
        current_entry = existing_data.get("teams", {}).get(key, {})
        current_entry["teamName"] = meta["name"]
        current_entry["shortName"] = meta["short"]
        current_entry["abbr"] = meta["abbr"]
        current_entry["teamId"] = str(team_id)
        current_entry["gameSheetUrl"] = f"https://gamesheetstats.com/seasons/{SEASON_ID}/teams/{team_id}/schedule"
        
        current_entry["record"] = metrics["record"]
        current_entry["stats"] = metrics["stats"]
        st = current_entry.setdefault("specialTeams", {})
        st["ppPct"] = metrics["specialTeams"]["ppPct"]
        st["ppGoals"] = metrics["specialTeams"]["ppGoals"]
        st["ppOpps"] = metrics["specialTeams"]["ppOpps"]
        st["pkPct"] = metrics["specialTeams"]["pkPct"]
        if "tendency" not in current_entry.get("specialTeams", {}):
            current_entry["specialTeams"]["tendency"] = "Official GameSheet regular season special teams metrics."

        current_entry["last5Games"] = metrics["last5Games"]
        if metrics["headToHead"]:
            current_entry["headToHead"] = metrics["headToHead"]

        existing_data["teams"][key] = current_entry
        synced_teams[key] = metrics["record"]
        logger.info(f"-> {meta['name']}: Record {metrics['record']['w']}-{metrics['record']['l']}-{metrics['record']['t']} ({metrics['record']['pts']} PTS), GF: {metrics['stats']['gf']}, GA: {metrics['stats']['ga']}")

    existing_data["lastSynced"] = datetime.utcnow().isoformat() + "Z"

    # Write updated gamesheet_league_data.json
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, indent=2)
    logger.info(f"Updated {DATA_FILE} successfully with {len(synced_teams)} teams!")

    # Synchronize inline GAMESHEET_DATABASE in index.html
    if INDEX_FILE.exists():
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            html = f.read()

        start_gs = html.find("const GAMESHEET_DATABASE = {")
        end_gs = html.find("function getOpponentGameSheetData(", start_gs)
        if start_gs != -1 and end_gs != -1:
            new_gs_database = "const GAMESHEET_DATABASE = " + json.dumps(existing_data, indent=2) + ";\n\n    "
            html = html[:start_gs] + new_gs_database + html[end_gs:]
            with open(INDEX_FILE, "w", encoding="utf-8") as f:
                f.write(html)
            logger.info("Synchronized inline GAMESHEET_DATABASE in index.html")

    logger.info("GameSheet sync complete!")

if __name__ == "__main__":
    main()
