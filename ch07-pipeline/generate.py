# -*- coding: utf-8 -*-
"""params.csv -> generated/run_<id>/scenario.txt

An AFSIM input file can only do text substitution ($define / $<X>$): no arithmetic, no loops,
no conditional branches (see documentation/html/docs/wsf_user_input_format.html).
So every parameter-to-coordinate conversion has to live in the generator.

Usage:
    python generate.py                    # read params.csv, render every row
    python generate.py --only 003         # render one row
    python generate.py --out generated    # write somewhere else

Outputs:
    generated/run_003/scenario.txt   the rendered scenario
    generated/run_003/output/        created in advance; mission.exe cannot open its log otherwise
    generated/run_003/manifest.json  parameter snapshot plus the template sha256, for traceability
    generated/index.csv              parameter index for every row
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "templates" / "scenario.tmpl"
PARAMS = HERE / "params.csv"

# the scenario origin; every offset is kilometres from it
ORIGIN_LAT = 30.0
ORIGIN_LON = 122.0
KM_PER_DEG_LAT = 111.32          # one degree of latitude is about 111.32 km, good to the 0.1 km level

PLACEHOLDER = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


def km_to_dms(north_km: float, east_km: float) -> tuple[str, str]:
    """Turn a kilometre offset from the origin into an AFSIM position string.

    position takes latitude then longitude; written longitude-first it reports Bad value for: position
    and exits with code 1. Latitude and longitude are formatted separately.
    """
    lat = ORIGIN_LAT + north_km / KM_PER_DEG_LAT
    lon = ORIGIN_LON + east_km / (KM_PER_DEG_LAT * math.cos(math.radians(ORIGIN_LAT)))
    return fmt_lat(lat), fmt_lon(lon)


def _fmt(value: float, hemi: str) -> str:
    sign = -1.0 if value < 0 else 1.0
    value = abs(value)
    deg = int(value)
    minutes = int((value - deg) * 60)
    seconds = (value - deg - minutes / 60.0) * 3600.0
    return f"{deg}:{minutes:02d}:{seconds:05.2f}{hemi if sign > 0 else hemi.swapcase()}"


def fmt_lat(lat: float) -> str:
    return _fmt(lat, "n")


def fmt_lon(lon: float) -> str:
    return _fmt(lon, "e")


def render(template: str, values: dict[str, str]) -> str:
    """One-pass substitution. string.Template is out: its $ delimiter collides with AFSIM's $define."""
    missing = sorted({name for name in PLACEHOLDER.findall(template) if name not in values})
    if missing:
        raise SystemExit(f"unsubstituted placeholders in the template: {', '.join(missing)}")
    return PLACEHOLDER.sub(lambda m: values[m.group(1)], template)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="render only this run_id")
    ap.add_argument("--out", default="generated")
    ap.add_argument("--clean", action="store_true", help="empty the output directory first")
    args = ap.parse_args()

    out_root = HERE / args.out
    if args.clean and out_root.exists():
        shutil.rmtree(out_root)      # only when asked; old artefacts are left alone by default
    out_root.mkdir(parents=True, exist_ok=True)

    template = TEMPLATE.read_text(encoding="utf-8")
    tpl_sha = hashlib.sha256(template.encode("utf-8")).hexdigest()[:12]

    # utf-8-sig: a CSV saved from Excel carries a BOM, which turns the first column into '\ufeffrun_id'
    rows = list(csv.DictReader(PARAMS.open(encoding="utf-8-sig")))
    index_rows = []

    for row in rows:
        run_id = row["run_id"].strip()
        if args.only and run_id != args.only:
            continue

        r0_km = float(row["r0_km"])
        aspect = math.radians(float(row["aspect_deg"]))
        # polar to north/east offsets: AFSIM cannot do this itself (no trigonometry, no expression evaluation)
        red_north = r0_km * math.cos(aspect)
        red_east = r0_km * math.sin(aspect)

        # Blue sits at the origin (a column may override it; with no column it is 0)
        blue_north = float(row.get("blue_north_km") or 0.0)
        blue_east = float(row.get("blue_east_km") or 0.0)
        blue_lat, blue_lon = km_to_dms(blue_north, blue_east)
        blue_lat_end, blue_lon_end = km_to_dms(blue_north, blue_east + 40.0)
        red_lat, red_lon = km_to_dms(red_north, red_east)
        # Red flies towards the origin, so the two sides close on each other
        red_lat_end, red_lon_end = km_to_dms(red_north * 0.35, red_east * 0.35)

        values = {
            "RUN_ID": run_id,
            "SEED": row["seed"].strip(),
            "R0_KM": f"{r0_km:.0f}",
            "BLUE_LAT": blue_lat,
            "BLUE_LON": blue_lon,
            "BLUE_LAT_END": blue_lat_end,
            "BLUE_LON_END": blue_lon_end,
            "RED_LAT": red_lat,
            "RED_LON": red_lon,
            "RED_LAT_END": red_lat_end,
            "RED_LON_END": red_lon_end,
            "RED_SPEED": row["red_speed_mps"].strip(),
            "FIRE_RANGE_M": f'{float(row["fire_range_km"]) * 1000.0:.0f}',
            "END_TIME": row["end_time_s"].strip(),
        }

        run_dir = out_root / f"run_{run_id}"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "output").mkdir(exist_ok=True)
        (run_dir / "scenario.txt").write_text(render(template, values), encoding="utf-8")
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "params": row,
                    "rendered_position": {
                        "blue": f"{blue_lat} {blue_lon}",
                        "red": f"{red_lat} {red_lon}",
                    },
                    "template_sha256_12": tpl_sha,
                    "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        index_rows.append({"run_id": run_id, **{k: v for k, v in values.items() if k != "RUN_ID"}})
        print(f"  run_{run_id}/scenario.txt  blue={blue_lat} {blue_lon}  red={red_lat} {red_lon}")

    if index_rows:
        with (out_root / "index.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(index_rows[0].keys()))
            writer.writeheader()
            writer.writerows(index_rows)

    print(f"rendered {len(index_rows)} scenarios, template sha256[:12] = {tpl_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
