# -*- coding: utf-8 -*-
"""Three gates: static check -> single-run smoke test -> statistical regression.

Usage:
    python gates.py                                   # gate 1 only (no engine)
    python gates.py --run-engine                      # gates 1 and 2
    python gates.py --run-engine --regress            # all three
    python gates.py --afsim-root ../../../afsim-2.9.0

Why three gates and not one:
  gate 1 catches writing it wrong, gate 2 catches a run that will not start or
  that starts and does nothing, gate 3 catches a run that works and does
  something but whose conclusion has moved.

Failure rates fall in that order and troubleshooting cost rises in it, so the gates
are ordered by cost. Exit code 0 if all pass, 1 if a gate fails; gate 3 only warns, unless --strict.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIB = HERE / "library"
GEN = HERE / "generated"
REPORTS = HERE / "reports"

# blocks that must be paired: only the commands listed here take part in the open/close check.
# note that end_time is a top-level command, not a close -- so end_ alone does not mean close.
BLOCKS = [
    "platform", "platform_type", "sensor", "weapon", "processor", "mover", "route",
    "event_output", "script_variables", "mode", "transmitter", "receiver",
    "execute", "script",
]
# files gate 1 skips (a generated artefact is guaranteed by its template; check for leftover placeholders only)
NAMING_TYPE = re.compile(r"^[A-Z][A-Z0-9_]*$")
NAMING_INSTANCE = re.compile(r"^[a-z][a-z0-9_]*$")


def rel(p: Path) -> str:
    p = p.resolve()
    try:
        return str(p.relative_to(HERE))
    except ValueError:
        return str(p)


# ---------------------------------------------------------------- gate 1
def gate1_static(files: list[Path]) -> list[tuple[bool, str, str]]:
    """Static check. Each finding is (passed, where, what)."""
    out = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()

        # (1) block closure: stack matching, reporting the first line that does not fit
        stack = []
        for no, line in enumerate(lines, 1):
            s = line.split("#", 1)[0].strip()
            if not s:
                continue
            head = s.split()[0]
            # edit <part type> <instance> is a block too, closed by end_<part type>
            if head == "edit" and len(s.split()) > 1:
                head = s.split()[1]
            if s.startswith("//") or s.startswith("/*"):
                continue
            if head in BLOCKS and not s.startswith("end_"):
                # a one-line block (sensor rdr1 GEO_RADAR end_sensor) is not an unclosed block
                if not s.endswith(f"end_{head}"):
                    stack.append((head, no))
            elif head.startswith("end_") and head[4:] in BLOCKS:
                name = head[4:]
                if not stack:
                    out.append((False, f"{rel(f)}:{no}", f"stray {head}"))
                elif stack[-1][0] != name:
                    want, at = stack[-1]
                    out.append((False, f"{rel(f)}:{no}", f"{head} does not pair with {want} on line {at}"))
                    stack.pop()
                else:
                    stack.pop()
        for name, no in stack:
            out.append((False, f"{rel(f)}:{no}", f"{name} has no matching end_{name}"))

        # (2) leftover placeholders
        if f.name == "scenario.txt" and "{{" in text:
            out.append((False, rel(f), "template placeholder was never substituted"))

        # (3) the first argument of position must be latitude, with an n/s suffix
        for no, line in enumerate(lines, 1):
            m = re.match(r"\s*position\s+(\S+)\s+(\S+)", line)
            if m:
                a, b = m.group(1).lower(), m.group(2).lower()
                if not a.endswith(("n", "s")) and b.endswith(("n", "s")):
                    out.append((False, f"{rel(f)}:{no}", "position looks longitude-first"))

        # (4) duplicated waypoints (the engine aborts with Coincident waypoints!)
        pts = re.findall(r"^\s*position\s+(\S+)\s+(\S+)", text, flags=re.M)
        if len(pts) != len(set(pts)):
            out.append((False, rel(f), "duplicated waypoints in this file"))

        # (5) tabs and CRLF, the two things that go bad first when a repository is shared
        if "\t" in text:
            out.append((False, rel(f), "contains a tab; indent with three spaces"))
        if "\r\n" in text:
            out.append((False, rel(f), "CRLF line endings; convert to LF before committing"))

    # (6) naming: type definitions and instances only
    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r"^\s*platform_type\s+(\S+)", text, flags=re.M):
            if not NAMING_TYPE.match(m.group(1)):
                out.append((False, rel(f), f"type name {m.group(1)} should be UPPER_SNAKE"))
        for m in re.finditer(r"^\s*platform\s+(\S+|\"[^\"]+\")\s+\S+", text, flags=re.M):
            name = m.group(1)
            if not NAMING_INSTANCE.match(name):
                out.append((False, rel(f), f"platform instance name {name} should be lower_snake"))

    # (7) event output needs an enable list (no list means zero bytes)
    for f in (p for p in files if p.name == "scenario.txt"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        if "event_output" in text and "enable " not in text:
            out.append((False, rel(f), "event_output has no enable list; the .evt will be zero bytes"))

    return out


# ---------------------------------------------------------------- gate 2
def gate2_smoke(afsim: Path, scenario: Path, timeout: float) -> list[tuple[bool, str, str]]:
    """Single-run smoke test: exit code, Simulation complete, a non-empty .evt, and the key event counts."""
    out = []
    exe = afsim / "bin" / "mission.exe"
    (scenario.parent / "output").mkdir(exist_ok=True)
    evt = scenario.parent / "output" / "scenario.evt"
    if evt.exists():
        evt.unlink()          # the old .evt must go first, or this reads the last artefact and passes a failure
    try:
        proc = subprocess.run(
            [str(exe), scenario.name],
            cwd=str(scenario.parent),
            capture_output=True,
            text=True,
            errors="ignore",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return [(False, rel(scenario), f"smoke test timed out (>{timeout:.0f}s)")]

    out.append((proc.returncode == 0, rel(scenario), f"exit code {proc.returncode}"))
    text = (proc.stdout or "") + (proc.stderr or "")
    out.append(("Simulation complete" in text, rel(scenario), "log carries Simulation complete"))

    size = evt.stat().st_size if evt.exists() else 0
    out.append((size > 0, rel(scenario), f".evt {size} bytes"))

    body = evt.read_text(encoding="utf-8", errors="ignore") if evt.exists() else ""
    n_track = body.count(" SENSOR_TRACK_INITIATED ")
    n_fired = body.count(" WEAPON_FIRED ")
    n_added = body.count(" PLATFORM_ADDED ")
    out.append((n_added >= 2, rel(scenario), f"PLATFORM_ADDED {n_added} (expected >= 2)"))
    out.append((n_track >= 1, rel(scenario), f"SENSOR_TRACK_INITIATED {n_track} (expected >= 1)"))
    out.append((n_fired >= 1, rel(scenario), f"WEAPON_FIRED {n_fired} (expected >= 1)"))
    return out


# ---------------------------------------------------------------- gate 3
# thresholds: metric -> (absolute tolerance, relative tolerance, direction)
THRESHOLDS = {
    "success_rate": (0.05, None, "ge"),      # no more than 5 points below the baseline
    "hit_rate":     (0.15, None, "abs"),     # absolute difference <= 0.15 (binomial noise over 24 runs is about +/-0.10)
    "detect_t_mean": (None, 0.20, "rel"),    # relative difference <= 20%
    "fire_t_mean":   (None, 0.10, "rel"),
}


def gate3_regress(current: dict, baseline: dict) -> list[tuple[bool, str, str]]:
    out = []
    for key, (abs_tol, rel_tol, mode) in THRESHOLDS.items():
        cur, base = current.get(key), baseline.get(key)
        if cur is None or base is None:
            out.append((True, key, "missing, skipped"))
            continue
        if mode == "ge":
            ok = cur >= base - abs_tol
            out.append((ok, key, f"{cur}, baseline {base}, floor {base - abs_tol:.3f}"))
        elif mode == "abs":
            diff = abs(cur - base)
            ok = diff <= abs_tol
            out.append((ok, key, f"{cur}, baseline {base}, |delta|={diff:.3f}, limit {abs_tol:.2f}"))
        else:
            diff = abs(cur - base) / base if base else 0.0
            ok = diff <= rel_tol
            out.append((ok, key, f"{cur}, baseline {base}, relative delta={diff * 100:.1f}%, limit {rel_tol * 100:.0f}%"))
    return out


def find_afsim(explicit: str | None) -> Path | None:
    cands = []
    if explicit:
        cands.append(Path(explicit))
    if os.environ.get("AFSIM_ROOT"):
        cands.append(Path(os.environ["AFSIM_ROOT"]))
    cands.append(HERE.parent.parent.parent / "afsim-2.9.0")
    for c in cands:
        if (c / "bin" / "mission.exe").exists():
            return c
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-engine", action="store_true")
    ap.add_argument("--regress", action="store_true")
    ap.add_argument("--strict", action="store_true", help="treat a gate 3 warning as a failure")
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--afsim-root", default=None)
    ap.add_argument("--extra", default=None, help="extra glob to scan, e.g. 'samples/*.txt'")
    ap.add_argument("--smoke", default=None, help="scenario for the smoke test (defaults to the first generated one)")
    args = ap.parse_args()

    files = sorted(LIB.rglob("*.txt")) + sorted(GEN.glob("run_*/scenario.txt"))
    if args.extra:
        files += sorted(HERE.glob(args.extra))
    if not files:
        raise SystemExit("library/ and generated/ are both empty; run generate.py first")

    report = []
    failed = 0

    print(f"[gate 1] static check on {len(files)} files")
    res = gate1_static(files)
    bad = [r for r in res if not r[0]]
    print(f"  {'pass' if not bad else f'{len(bad)} problems'}")
    for ok, where, msg in bad:
        print(f"  [FAIL] {where}  {msg}")
    report.append(("gate 1 static check", not bad, f"{len(files)} files / {len(bad)} problems"))
    failed += 1 if bad else 0

    if args.run_engine:
        afsim = find_afsim(args.afsim_root)
        if not afsim:
            print("[gate 2] AFSIM not found, skipped")
            report.append(("gate 2 smoke test", True, "skipped"))
        else:
            target = Path(args.smoke) if args.smoke else sorted(GEN.glob("run_*/scenario.txt"))[0]
            print(f"[gate 2] smoke test {rel(target)}")
            res = gate2_smoke(afsim, target, args.timeout)
            bad = [r for r in res if not r[0]]
            for ok, where, msg in res:
                print(f"  [{'OK  ' if ok else 'FAIL'}] {msg}")
            report.append(("gate 2 smoke test", not bad, f"{len(bad)} checks unmet"))
            failed += 1 if bad else 0

    if args.regress:
        cur_p, base_p = REPORTS / "batch_summary.json", REPORTS / "baseline.json"
        print(f"[gate 3] statistical regression {rel(cur_p)} vs {rel(base_p)}")
        if not cur_p.exists() or not base_p.exists():
            print(f"  [WARN] {rel(base_p)} missing; run batch_run.py and copy it to baseline.json")
            report.append(("gate 3 statistical regression", True, "skipped (no baseline)"))
        else:
            res = gate3_regress(
                json.loads(cur_p.read_text(encoding="utf-8")),
                json.loads(base_p.read_text(encoding="utf-8")),
            )
            bad = [r for r in res if not r[0]]
            for ok, key, msg in res:
                print(f"  [{'OK  ' if ok else 'WARN'}] {key}: {msg}")
            report.append(("gate 3 statistical regression", not bad or not args.strict, f"{len(bad)} checks over threshold"))
            failed += 1 if (bad and args.strict) else 0

    REPORTS.mkdir(exist_ok=True)
    lines = ["Three-gate report", "=" * 40]
    for name, ok, note in report:
        lines.append(f"{'PASS' if ok else 'FAIL'}  {name}  {note}")
    lines.append(f"\nverdict: {'pass' if not failed else f'{failed} gate(s) failed'}")
    (REPORTS / "gates_report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nverdict: {'pass' if not failed else f'{failed} gate(s) failed'}  -> {rel(REPORTS / 'gates_report.txt')}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
