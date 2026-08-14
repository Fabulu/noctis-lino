#!/usr/bin/env python3
"""Score the production Lino generator against the public NIVGEN sheet."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import nivtest  # noqa: E402


API = "https://litterbox.moos.es/sheets/nivgen_planets?page=1&pageSize=2000"
COORDS = re.compile(r"orig_surface_(-?\d+)_(-?\d+)_(-?\d+)_([0-9]+)\.png")
FIELDS = (
    "surf", "atmo", "pal", "sect_def_hm", "sect_def_oc",
    "sect_def_stex", "sect_def_sky", "sect_rand_hm", "sect_rand_oc",
    "sect_rand_stex", "sect_rand_sky",
)


def fetch_rows(url: str, attempts: int, delay: float) -> list[dict[str, object]]:
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                payload = json.load(response)
            break
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == attempts:
                raise
            wait = min(30.0, delay * attempt)
            print(f"sheet fetch {attempt}/{attempts} failed: {error}; "
                  f"retrying in {wait:g}s", file=sys.stderr, flush=True)
            time.sleep(wait)
    names = [column["name"] for column in payload["columns"]]
    return [dict(zip(names, row)) for row in payload["rows"]]


def coordinates(row: dict[str, object]) -> tuple[int, int, int, int]:
    url = str(row.get("orig_surface_url") or "")
    match = COORDS.search(url)
    if not match:
        raise ValueError(f"row {row.get('key')} has no parseable original URL")
    return tuple(map(int, match.groups()))  # type: ignore[return-value]


def namespace(args: argparse.Namespace, x: int, y: int, z: int, body: int,
              lon: int, lat: int, gap: str | None, build: bool):
    return argparse.Namespace(
        x=x, y=y, z=z, p=body, lon=lon, lat=lat, secs=0, sc=-1,
        albedo=-1, night=0, gap=gap, build=build, timeout=args.timeout,
        dump=None, o=None,
    )


def run_site(args: argparse.Namespace, coords: tuple[int, int, int, int],
             lon: int, lat: int, gap: str | None, build: bool):
    call = namespace(args, *coords, lon, lat, gap, build)
    header, buffers = nivtest.run_lino(call)
    return nivtest.results(header, buffers)


def grade_row(args: argparse.Namespace, row: dict[str, object], build: bool):
    coords = coordinates(row)
    default = run_site(args, coords, 0, 60,
                       str(row.get("orig_sect_def_gap") or "") or None,
                       build)
    random = None
    if not args.planet_only:
        random = run_site(
            args, coords, int(row["rand_lon"]), int(row["rand_lat"]),
            str(row.get("orig_sect_rand_gap") or "") or None, False)
    got = {
        "surf": default["hashes"]["surf"]["fnv"],
        "atmo": default["hashes"]["atmo"]["fnv"],
        "pal": default["hashes"]["pal"]["fnv"],
        "sect_def_hm": default["hashes"]["hm"]["fnv"],
        "sect_def_oc": default["hashes"]["oc"]["fnv"],
        "sect_def_stex": default["hashes"]["stex"]["fnv"],
        "sect_def_sky": default["hashes"]["sky"]["fnv"],
    }
    if random is not None:
        got.update({
            "sect_rand_hm": random["hashes"]["hm"]["fnv"],
            "sect_rand_oc": random["hashes"]["oc"]["fnv"],
            "sect_rand_stex": random["hashes"]["stex"]["fnv"],
            "sect_rand_sky": random["hashes"]["sky"]["fnv"],
        })
    comparisons = {}
    for field, value in got.items():
        expected = row.get("orig_" + field)
        comparisons[field] = {
            "got": value, "expected": expected,
            "match": expected is not None and value == expected,
        }
    return {
        "key": row["key"], "type": row["type"], "coords": coords[:3],
        "body": coords[3], "reported_type": default["type"],
        "sheet_seedval": row.get("seedval"), "lino_seedval": default["seedval"],
        "global_surface_seed": default["global_surface_seed"],
        "comparisons": comparisons,
    }


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compare real Lino generator hashes to NIVGEN originals")
    parser.add_argument("--url", default=API)
    parser.add_argument("--type", type=int, action="append", dest="types")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=1,
                        help="rows to execute; defaults to one deliberate smoke")
    parser.add_argument("--planet-only", action="store_true")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--fetch-attempts", type=int, default=5)
    parser.add_argument("--fetch-delay", type=float, default=2.0)
    parser.add_argument("--json-out")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = fetch_rows(args.url, max(1, args.fetch_attempts),
                      max(0.0, args.fetch_delay))
    if args.types:
        wanted = set(args.types)
        rows = [row for row in rows if int(row["type"]) in wanted]
    rows = rows[args.start:args.start + args.limit]
    reports = []
    counts = Counter()
    build = args.build
    for index, row in enumerate(rows, 1):
        report = grade_row(args, row, build)
        build = False
        reports.append(report)
        comparisons = report["comparisons"]
        matched = sum(1 for item in comparisons.values() if item["match"])
        print(f"[{index}/{len(rows)}] {report['key']} type={report['type']} "
              f"matched={matched}/{len(comparisons)}")
        for field, item in comparisons.items():
            counts[field, bool(item["match"])] += 1
            if not item["match"]:
                print(f"  {field}: {item['got']} != {item['expected']}")
    total = sum(value for (field, match), value in counts.items() if match)
    graded = sum(counts.values())
    print(f"TOTAL exact={total}/{graded} rows={len(reports)}")
    for field in FIELDS:
        yes = counts[field, True]
        no = counts[field, False]
        if yes or no:
            print(f"  {field}: {yes}/{yes + no}")
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps({"reports": reports, "exact": total, "graded": graded},
                       indent=2) + "\n",
            encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
