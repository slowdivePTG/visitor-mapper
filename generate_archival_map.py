#!/usr/bin/env python3
"""
Generate the static archival visitor-map HTML.

    python generate_archival_map.py                     # local JSON dump
    python generate_archival_map.py --live               # query live DB first

Reads a local JSON dump of visitor records (exported from the Neon Postgres DB)
and produces a self-contained HTML file at assets/cached-visitor-map.html.

Expected JSON format:
    [{ "latitude": 41.88, "longitude": -87.63,
       "city": "Chicago", "country": "United States",
       "timestamp": "2024-01-15T10:30:00Z" }, …]

The output file is committed to the repo and served by GitHub Pages as a static asset.
"""

import argparse
import json
import os
import sys

# Ensure numpy / scipy / global-land-mask are available before importing
try:
    from map_render import generate_globe_map, _get_land_skeleton
except ImportError as e:
    print(f"Error: {e}")
    print("Make sure the required dependencies are installed:")
    print("  pip install numpy scipy global-land-mask")
    sys.exit(1)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ASSETS_DIR = os.path.join(REPO_ROOT, "assets")
DEFAULT_INPUT = os.path.join(os.path.dirname(__file__), "visitors_export.json")
ARCHIVAL_OUT = os.path.join(ASSETS_DIR, "cached-visitor-map.html")


def load_records(path):
    """Load visitor records from a local JSON dump file."""
    if not os.path.exists(path):
        print(f"Error: input file not found: {path}")
        sys.exit(1)

    with open(path) as f:
        raw = json.load(f)

    if not isinstance(raw, list):
        print("Error: expected a JSON array at the top level")
        sys.exit(1)

    records = []
    for item in raw:
        lat = item.get("latitude")
        lon = item.get("longitude")
        city = item.get("city", "Unknown City")
        country = item.get("country", "")
        ts = item.get("timestamp", "")
        if lat is not None and lon is not None:
            records.append((lat, lon, city, country, ts))

    print(f"Loaded {len(records)} visitor records from {path}")
    return records


def fetch_live_records():
    """Query the Neon Postgres DB directly and return (records, path_to_dump)."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("Error: python-dotenv is required for --live mode.")
        print("  pip install python-dotenv")
        sys.exit(1)

    try:
        from database import get_db_connection
    except ImportError:
        print("Error: database.py not found in the same directory.")
        sys.exit(1)

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT latitude, longitude, city, country, timestamp "
            "FROM visitors ORDER BY timestamp DESC"
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    print(f"Fetched {len(rows)} records from the database.")

    # Also dump to JSON for offline use
    dump = []
    for lat, lon, city, country, ts in rows:
        dump.append({
            "latitude": lat,
            "longitude": lon,
            "city": city,
            "country": country,
            "timestamp": str(ts) if ts is not None else "",
        })

    dump_path = DEFAULT_INPUT
    with open(dump_path, "w") as f:
        json.dump(dump, f, indent=2)
    print(f"Dumped {len(dump)} records to {dump_path}")

    return rows, dump_path


def main():
    parser = argparse.ArgumentParser(description="Generate static archival visitor-map HTML")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Query the live Neon Postgres DB instead of a local JSON file",
    )
    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT,
        help=f"Path to the JSON dump (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output",
        default=ARCHIVAL_OUT,
        help=f"Output path (default: {ARCHIVAL_OUT})",
    )
    args = parser.parse_args()

    # Pre-warm the land-skeleton cache so the first render is fast
    print("Pre-loading land skeleton …")
    _get_land_skeleton()

    if args.live:
        records, _ = fetch_live_records()
        label = "archival (live)"
    else:
        records = load_records(args.input)
        label = "archival"

    html = generate_globe_map(records)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        f.write(html)

    print(f"Saved {label} map to {args.output}")


if __name__ == "__main__":
    main()
