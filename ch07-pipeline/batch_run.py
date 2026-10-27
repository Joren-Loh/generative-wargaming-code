# -*- coding: utf-8 -*-
"""Concurrent batch runs, plus the results summary.

Usage:
    python batch_run.py                          # 4 workers, 4 runs per scenario
    python batch_run.py --workers 6 --repeats 4
    python batch_run.py --timeout 30 --afsim-root ../../../afsim-2.9.0

The unit of parallelism is the scenario directory, not the single run: repeats of
one scenario must run in series, because they share the fixed name output/scenario.evt
(hard-coded in the scenario) and would overwrite each other. Across scenarios in parallel, within a scenario in series: the cheapest split that avoids the clash.

Each run overrides the seed through a second input file, leaving the rendered scenario alone:
    mission.exe scenario.txt output/_seed_<k>.txt      # the second file holds one random_seed line
AFSIM reads its input files in order, and the last random_seed wins (measured here).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from statistics import mean, pstdev

HERE = Path(__file__).resolve().parent
GENERATED = HERE / "generated"
REPORTS = HERE / "reports"

# key line prefixes in the .evt -> metric names
T_TRACK = re.compile(r"^(\d+\.\d+)\s+SENSOR_TRACK_INITIATED\b")
T_FIRED = re.compile(r"^(\d+\.\d+)\s+WEAPON_FIRED\b")


def find_afsim(explicit: str | None) -> Path:
    cands = []
    if explicit:
        cands.append(Path(explicit))
    if os.environ.get("AFSIM_ROOT"):
        cands.append(Path(os.environ["AFSIM_ROOT"]))
    cands.append(HERE.parent.parent.parent / "afsim-2.9.0")
    for c in cands:
        if (c / "bin" / "mission.exe").exists():
            return c
    raise SystemExit("AFSIM not found: pass --afsim-root or set AFSIM_ROOT")


def parse_evt(evt: Path) -> dict:
    """Extract metrics from the .evt. Match the leading event type only, no regex soup, and skip bad lines."""
    out = {"evt_lines": 0, "evt_bytes": 0, "first_track_t": "", "first_fire_t": "",
           "n_fired": 0, "hit": 0}
    if not evt.exists():
        return out
    out["evt_bytes"] = evt.stat().st_size
    n_hit = 0
    with evt.open(encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.strip():
                continue
            out["evt_lines"] += 1
            m = T_TRACK.match(line)
            if m and not out["first_track_t"]:
                out["first_track_t"] = m.group(1)
            m = T_FIRED.match(line)
            if m:
                out["n_fired"] += 1
                if not out["first_fire_t"]:
                    out["first_fire_t"] = m.group(1)
            elif " WEAPON_HIT " in line:
                n_hit += 1
    out["hit"] = 1 if n_hit else 0
    return out


def run_one(work: Path, exe: Path, repeat_idx: int, seed: int, timeout: float) -> dict:
    """Run one game. Any exception becomes a FAIL row: nothing is raised, nothing leaks into other runs."""
    out_dir = work / "output"
    out_dir.mkdir(exist_ok=True)
    seed_file = out_dir / f"_seed_{repeat_idx}.txt"
    seed_file.write_text(f"random_seed {seed}\n", encoding="ascii")
    evt = out_dir / "scenario.evt"
    if evt.exists():
        evt.unlink()               # the old .evt must go, or a failed run reads the previous artefact

    row = {
        "run_id": work.name.replace("run_", ""),
        "repeat": repeat_idx,
        "seed": seed,
        "rc": "",
        "wall_s": "",
        "status": "",
        "note": "",
    }
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            [str(exe), "scenario.txt", str(seed_file)],
            cwd=str(work),
            capture_output=True,
            text=True,
            errors="ignore",
            timeout=timeout,
        )
        row["wall_s"] = f"{time.perf_counter() - t0:.2f}"
        row["rc"] = proc.returncode
        out = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0:
            row["status"] = "FAIL"
            row["note"] = first_error(out)
        elif "Simulation complete" not in out:
            row["status"] = "FAIL"
            row["note"] = "no 'Simulation complete'"
        else:
            row["status"] = "OK"
    except subprocess.TimeoutExpired:
        row["wall_s"] = f"{time.perf_counter() - t0:.2f}"
        row["rc"] = "timeout"
        row["status"] = "FAIL"
        row["note"] = f"did not finish within {timeout:.0f}s"
    row.update(parse_evt(evt))
    return row


def first_error(text: str) -> str:
    for line in text.splitlines():
        if "ERROR" in line or "FATAL" in line:
            return line.strip()[:100]
    return "see output/scenario.log"


def summarize(rows: list[dict]) -> dict:
    ok = [r for r in rows if r["status"] == "OK"]
    det = [float(r["first_track_t"]) for r in ok if r["first_track_t"] not in ("", None)]
    fire = [float(r["first_fire_t"]) for r in ok if r["first_fire_t"] not in ("", None)]
    walls = [float(r["wall_s"]) for r in rows if r["wall_s"] not in ("", None)]
    hits = [r["hit"] for r in ok]
    return {
        "runs": len(rows),
        "ok": len(ok),
        "success_rate": round(len(ok) / len(rows), 4) if rows else 0.0,
        "wall_total_s": round(sum(walls), 2),
        "wall_mean_s": round(mean(walls), 3) if walls else 0.0,
        "detect_t_mean": round(mean(det), 3) if det else None,
        "detect_t_std": round(pstdev(det), 3) if len(det) > 1 else 0.0,
        "fire_t_mean": round(mean(fire), 3) if fire else None,
        "fire_t_std": round(pstdev(fire), 3) if len(fire) > 1 else 0.0,
        "hit_rate": round(mean(hits), 3) if hits else 0.0,
        "fired_mean": round(mean([r["n_fired"] for r in ok]), 2) if ok else 0.0,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--repeats", type=int, default=4, help="runs per scenario")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--afsim-root", default=None)
    args = ap.parse_args()

    afsim = find_afsim(args.afsim_root)
    exe = afsim / "bin" / "mission.exe"
    works = sorted(p for p in GENERATED.glob("run_*") if (p / "scenario.txt").exists())
    if not works:
        raise SystemExit("no scenarios under generated/; run generate.py first")

    REPORTS.mkdir(exist_ok=True)
    jobs = []
    for work in works:
        manifest = json.loads((work / "manifest.json").read_text(encoding="utf-8"))
        base = int(manifest["params"]["seed"])
        for k in range(args.repeats):
            jobs.append((work, k, base + 1000 * k))

    print(f"engine {exe}\n{len(works)} scenarios x {args.repeats} runs = {len(jobs)} runs,"
          f"{args.workers} workers, {args.timeout:.0f}s per run")

    t0 = time.perf_counter()
    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        # one task per scenario directory; inside a task its repeats run in series
        futures = {
            pool.submit(run_series, work, exe, args.repeats, args.timeout, jobs): work
            for work in works
        }
        for fut in as_completed(futures):
            work = futures[fut]
            got = fut.result()
            rows.extend(got)
            bad = sum(1 for r in got if r["status"] != "OK")
            print(f"  {work.name}: {len(got) - bad}/{len(got)} succeeded")
    wall = time.perf_counter() - t0

    rows.sort(key=lambda r: (r["run_id"], r["repeat"]))
    csv_path = REPORTS / "batch_results.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary = summarize(rows)
    summary["wall_parallel_s"] = round(wall, 2)
    summary["workers"] = args.workers
    (REPORTS / "batch_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\nsummary -> {csv_path.relative_to(HERE)}")
    print(f"  runs {summary['runs']}, succeeded {summary['ok']} ({summary['success_rate'] * 100:.1f}%)")
    print(f"  wall clock in series {summary['wall_total_s']}s, in parallel {summary['wall_parallel_s']}s,"
          f"speed-up {summary['wall_total_s'] / summary['wall_parallel_s']:.1f}x")
    print(f"  mean per run {summary['wall_mean_s']}s")
    if summary["detect_t_mean"] is not None:
        print(f"  first detection {summary['detect_t_mean']} +/- {summary['detect_t_std']} s")
    if summary["fire_t_mean"] is not None:
        print(f"  first launch {summary['fire_t_mean']} +/- {summary['fire_t_std']} s")
    print(f"  hit rate {summary['hit_rate'] * 100:.1f}%, mean launches {summary['fired_mean']}")
    print(f"  → {REPORTS / 'batch_summary.json'}")
    return 0


def run_series(work: Path, exe: Path, repeats: int, timeout: float, jobs) -> list[dict]:
    got = []
    seeds = {k: s for w, k, s in jobs if w == work}
    for k in range(repeats):
        r = run_one(work, exe, k, seeds[k], timeout)
        got.append(r)
    return got


if __name__ == "__main__":
    sys.exit(main())
