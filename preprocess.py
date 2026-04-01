"""
LILA BLACK - Player Data Preprocessor
======================================
Reads all .nakama-0 parquet files from player_data/ directory,
transforms world coordinates to minimap pixel coordinates,
and outputs JSON files the browser tool can load directly.

Run this once:
    python preprocess.py --data ./player_data --out ./data

Output files:
    data/AmbroseValley.json
    data/GrandRift.json
    data/Lockdown.json
    data/meta.json
"""

import os
import sys
import json
import argparse
import math
from pathlib import Path

import pyarrow.parquet as pq
import pandas as pd

# ── Map configuration (from README) ──────────────────────────────────────────
# Each map has a scale and origin that maps 3D world coords to 0-1 UV space,
# then multiplied by 1024 to get pixel position on the minimap image.
#
# Formula (from README):
#   u = (x - origin_x) / scale
#   v = (z - origin_z) / scale
#   pixel_x = u * 1024
#   pixel_y = (1 - v) * 1024   ← Y flipped because image origin is top-left

MAP_CONFIG = {
    "AmbroseValley": {"scale": 900,  "origin_x": -370, "origin_z": -473},
    "GrandRift":     {"scale": 581,  "origin_x": -290, "origin_z": -290},
    "Lockdown":      {"scale": 1000, "origin_x": -500, "origin_z": -500},
}

# ── Event type categories for the frontend ────────────────────────────────────
# Grouped so the UI can toggle layers independently
EVENT_CATEGORIES = {
    "Position":       "path",
    "BotPosition":    "path",
    "Kill":           "kill",
    "Killed":         "death",
    "BotKill":        "kill",
    "BotKilled":      "death",
    "KilledByStorm":  "storm",
    "Loot":           "loot",
}


def world_to_pixel(x, z, map_id):
    """Convert 3D world coordinates to 2D minimap pixel coordinates."""
    cfg = MAP_CONFIG[map_id]
    u = (x - cfg["origin_x"]) / cfg["scale"]
    v = (z - cfg["origin_z"]) / cfg["scale"]
    px = round(u * 1024, 1)
    py = round((1 - v) * 1024, 1)
    return px, py


def is_bot(user_id):
    """Bots have numeric user IDs (e.g. '1440'), humans have UUIDs."""
    return str(user_id).replace("_", "").isdigit() or (
        len(str(user_id)) < 10 and str(user_id).isdigit()
    )


def decode_event(val):
    """Event column is stored as bytes in parquet — decode to string."""
    if isinstance(val, bytes):
        return val.decode("utf-8")
    return str(val)


def load_file(filepath):
    """Read a single .nakama-0 parquet file into a DataFrame."""
    try:
        table = pq.read_table(str(filepath))
        df = table.to_pandas()
        # Decode bytes columns
        df["event"] = df["event"].apply(decode_event)
        if "map_id" in df.columns and df["map_id"].dtype == object:
            df["map_id"] = df["map_id"].apply(
                lambda v: v.decode("utf-8") if isinstance(v, bytes) else str(v)
            )
        if "user_id" in df.columns:
            df["user_id"] = df["user_id"].apply(
                lambda v: v.decode("utf-8") if isinstance(v, bytes) else str(v)
            )
        if "match_id" in df.columns:
            df["match_id"] = df["match_id"].apply(
                lambda v: v.decode("utf-8") if isinstance(v, bytes) else str(v)
            )
        return df
    except Exception as e:
        print(f"  ⚠ Skipping {filepath.name}: {e}")
        return None


def ts_to_ms(ts_val):
    """Convert timestamp to milliseconds integer for the timeline slider."""
    try:
        if hasattr(ts_val, "value"):
            # pandas Timestamp nanoseconds → ms
            return int(ts_val.value // 1_000_000)
        return int(ts_val)
    except Exception:
        return 0


def process_all(data_dir, out_dir):
    data_path = Path(data_dir)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Collect all .nakama-0 files grouped by date folder
    day_folders = sorted([
        d for d in data_path.iterdir()
        if d.is_dir() and d.name.startswith("February")
    ])

    print(f"Found {len(day_folders)} day folders")

    # Per-map data store
    # Structure: map_id → date → match_id → list of player journeys
    maps_data = {m: {} for m in MAP_CONFIG}

    total_files = 0
    skipped = 0

    for day_dir in day_folders:
        date_label = day_dir.name  # e.g. "February_10"
        files = list(day_dir.glob("*.nakama-0"))
        print(f"\n📅 {date_label}: {len(files)} files")

        for fpath in files:
            total_files += 1

            # Parse user_id and match_id from filename
            # Format: {user_id}_{match_id}.nakama-0
            stem = fpath.stem  # strips .nakama-0
            # Match ID is always a UUID (5 groups separated by -)
            # User ID is either a UUID or a short number
            # Split on first underscore that precedes a UUID pattern
            parts = stem.split("_")

            # Reconstruct: find the boundary between user_id and match_id
            # match_id always ends with ".nakama-0" already stripped
            # A UUID has 5 dash-separated groups: 8-4-4-4-12
            # Try splitting from the right to find the match UUID
            match_id = None
            user_id = None

            # Try: last 5 parts form the match UUID
            for split_point in range(len(parts) - 1, 0, -1):
                candidate_match = "_".join(parts[split_point:])
                candidate_user = "_".join(parts[:split_point])
                # A UUID has exactly 4 dashes
                if candidate_match.count("-") == 4:
                    match_id = candidate_match
                    user_id = candidate_user
                    break

            if not match_id:
                skipped += 1
                continue

            df = load_file(fpath)
            if df is None or df.empty:
                skipped += 1
                continue

            # Get map from first row (all rows in file have same map)
            map_id = str(df["map_id"].iloc[0])
            if map_id not in MAP_CONFIG:
                skipped += 1
                continue

            bot = is_bot(user_id)

            # Build event list — convert coords, keep only needed fields
            events = []
            for _, row in df.iterrows():
                evt_raw = row["event"]
                evt_type = decode_event(evt_raw)
                category = EVENT_CATEGORIES.get(evt_type, "other")

                x = float(row["x"]) if pd.notna(row["x"]) else 0.0
                z = float(row["z"]) if pd.notna(row["z"]) else 0.0
                px, py = world_to_pixel(x, z, map_id)

                # Skip out-of-bounds pixels (bad data / outside map)
                if not (0 <= px <= 1024 and 0 <= py <= 1024):
                    continue

                events.append({
                    "t":  ts_to_ms(row["ts"]),
                    "px": px,
                    "py": py,
                    "type": evt_type,
                    "cat":  category,
                })

            if not events:
                skipped += 1
                continue

            # Sort by timestamp so playback works correctly
            events.sort(key=lambda e: e["t"])

            # Store in map → date → match structure
            if date_label not in maps_data[map_id]:
                maps_data[map_id][date_label] = {}

            if match_id not in maps_data[map_id][date_label]:
                maps_data[map_id][date_label][match_id] = []

            maps_data[map_id][date_label][match_id].append({
                "user_id":  user_id,
                "is_bot":   bot,
                "events":   events,
            })

    print(f"\n✅ Loaded {total_files - skipped}/{total_files} files ({skipped} skipped)")

    # ── Write per-map JSON files ──────────────────────────────────────────────
    meta = {"maps": {}}

    for map_id, dates in maps_data.items():
        total_matches = sum(len(m) for m in dates.values())
        total_players = sum(
            len(players)
            for d in dates.values()
            for players in d.values()
        )
        total_events = sum(
            len(p["events"])
            for d in dates.values()
            for players in d.values()
            for p in players
        )

        print(f"\n🗺  {map_id}: {total_matches} matches, {total_players} player journeys, {total_events} events")

        # Convert to list format for the frontend
        out_matches = []
        for date_label, matches in sorted(dates.items()):
            for match_id, players in matches.items():
                # Compute match time range for timeline
                all_ts = [e["t"] for p in players for e in p["events"]]
                ts_min = min(all_ts) if all_ts else 0
                ts_max = max(all_ts) if all_ts else 0

                human_count = sum(1 for p in players if not p["is_bot"])
                bot_count = sum(1 for p in players if p["is_bot"])

                out_matches.append({
                    "match_id":     match_id,
                    "date":         date_label,
                    "ts_min":       ts_min,
                    "ts_max":       ts_max,
                    "human_count":  human_count,
                    "bot_count":    bot_count,
                    "players":      players,
                })

        out_file = out_path / f"{map_id}.json"
        with open(out_file, "w") as f:
            json.dump(out_matches, f, separators=(",", ":"))

        size_kb = out_file.stat().st_size // 1024
        print(f"   → Wrote {out_file.name} ({size_kb} KB)")

        meta["maps"][map_id] = {
            "matches":       total_matches,
            "player_files":  total_players,
            "events":        total_events,
            "dates":         sorted(dates.keys()),
            "file":          f"{map_id}.json",
        }

    # Write meta.json for the frontend to discover available maps/dates
    meta_file = out_path / "meta.json"
    with open(meta_file, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"\n📄 Wrote meta.json")
    print("\n🎉 Preprocessing complete. Run a local server and open index.html")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LILA BLACK data preprocessor")
    parser.add_argument("--data", default="./player_data",
                        help="Path to player_data folder (default: ./player_data)")
    parser.add_argument("--out",  default="./data",
                        help="Output directory for JSON files (default: ./data)")
    args = parser.parse_args()

    if not Path(args.data).exists():
        print(f"❌ Data directory not found: {args.data}")
        sys.exit(1)

    process_all(args.data, args.out)
