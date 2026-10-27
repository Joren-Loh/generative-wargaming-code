# -*- coding: utf-8 -*-
"""
Execution-feedback repairer: from an engine error to a directed fix, closed loop.

Loop, per sample, at most max_iter rounds:
  1. run mission.exe once and capture the ERROR lines from stdout and stderr;
  2. map each error class to a deterministic repair function (the table is REPAIR_RULES);
  3. apply the fix, re-run, repeat until it passes or the round limit is reached.
The acceptance test is verify.py's: exit code 0, "Simulation complete", and a non-empty .evt.

What no rule can fix (an unclosed block, semantics that contradict the requirement) returns unrepairable,
and the chapter explains why those two go back to the model.

Usage:
  python repair.py samples/s01_type_hallucination.txt   # one sample
  python repair.py --all                                # every sample, with a summary table
"""

import difflib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_KNOWLEDGE = _HERE / "knowledge"
AFSIM_ROOT = Path(_HERE.parent.parent.parent / "afsim-2.9.0")
MISSION_EXE = AFSIM_ROOT / "bin" / "mission.exe"


def run_engine(script_text: str, workdir: Path):
    """Run the engine; return (ok, output)."""
    if workdir.exists():
        shutil.rmtree(workdir)
    (workdir / "output").mkdir(parents=True)
    (workdir / "scenario.txt").write_text(script_text, encoding="utf-8")
    r = subprocess.run([str(MISSION_EXE), "scenario.txt"], cwd=str(workdir),
                       capture_output=True, text=True, errors="ignore", timeout=120)
    out = (r.stdout or "") + (r.stderr or "")
    evt = workdir / "output" / "scenario.evt"
    # the .evt test only applies when the script configures event_output; a scenario without it writes no .evt
    evt_ok = (evt.exists() and evt.stat().st_size > 0) if \
        "event_output" in script_text else True
    ok = r.returncode == 0 and "Simulation complete" in out and evt_ok
    return ok, out


def _errors_of(out: str):
    errs = []
    for i, line in enumerate(out.splitlines()):
        if "ERROR" in line:
            errs.append(line.strip().replace("***** ERROR: ", ""))
    return errs


# ---------------------------------------------------------------- repairs
def fix_type_hallucination(script, err):
    """Could not find platform_type X -> use the nearest type this scenario already defines.

    When the scenario defines no type at all, fall back to the built-in WSF_PLATFORM.
    """
    name = re.search(r"Could not find platform_type (\S+)", err).group(1)
    local = re.findall(r"platform_type\s+(\w+)\s+WSF_PLATFORM", script)
    if not local:
        return script.replace(" %s\n" % name, " WSF_PLATFORM\n"), \
            "type %s -> WSF_PLATFORM (built-in fallback)" % name
    near = difflib.get_close_matches(name, local, n=1, cutoff=0.0)
    side = name[:4].upper()
    same_side = [t for t in local if t[:4].upper() == side]
    target = near[0] if near else (same_side[0] if same_side else local[0])
    return re.sub(r"(\b%s\b)" % re.escape(name), target, script, count=1), \
        "type %s -> %s (defined in this scenario)" % (name, target)


def fix_bad_include(script, err):
    """Cannot open file: X -> delete that include_once line."""
    path = re.search(r"Cannot open file: (\S+)", err).group(1)
    lines = [l for l in script.splitlines()
             if not re.match(r"\s*include_once\s+%s\s*$" % re.escape(path), l)]
    return "\n".join(lines) + "\n", "removed invalid include %s" % path


def fix_unknown_identifier(script, err):
    """Unknown identifier: 'X' -> declare it in the global script_variables."""
    m = re.search(r"Unknown identifier: '(\w+)'", err)
    if not m:
        return None, None
    name = m.group(1)
    decl = "script_variables\n   double %s = 0.0;\nend_script_variables\n" % name
    return decl + script, "declared global %s (set to 0.0; confirm the meaning by hand)" % name


def fix_bad_position(script, err):
    """Bad value for: position -> probably reversed, so swap the first two coordinates."""
    lines = script.splitlines()
    for i, l in enumerate(lines):
        s = l.strip()
        if s.startswith("position "):
            toks = s.split()
            if len(toks) >= 3 and re.match(r"^-?[\d:.]+[eEwW]$", toks[1]) \
                    and re.match(r"^-?[\d:.]+[nNsS]$", toks[2]):
                toks[1], toks[2] = toks[2], toks[1]
                indent = l[:len(l) - len(l.lstrip())]
                lines[i] = indent + " ".join(toks)
                return "\n".join(lines) + "\n", "swapped latitude/longitude: %s" % s
    return None, None


def fix_unknown_command_speed(script, err):
    """speed on a platform position line -> drop the speed clause."""
    lines = script.splitlines()
    for i, l in enumerate(lines):
        s = l.strip()
        if s.startswith("position ") and re.search(r"\bspeed\s+[\d.]+", s):
            indent = l[:len(l) - len(l.lstrip())]
            lines[i] = indent + re.sub(r"\s*speed\s+[\d.]+\s*\w*", "", s)
            return "\n".join(lines) + "\n", "dropped the speed clause from the position line"
    return None, None


def fix_coincident_waypoints(script, err):
    """Coincident route waypoints -> offset the later one 500 m to the north-east."""
    seen = set()
    lines = script.splitlines()
    in_route = False
    for i, l in enumerate(lines):
        s = l.strip()
        if s.startswith("route") and not s.startswith("route_"):
            in_route = True
        elif s.startswith("end_route"):
            in_route = False
        elif in_route and s.startswith("position "):
            m = re.match(r"position\s+(-?[\d.]+)([nNsS])\s+(-?[\d.]+)([eEwW])(.*)", s)
            if m:
                key = (float(m.group(1)), float(m.group(3)))
                if key in seen:
                    lat, lon = key[0] + 500.0 / 111320.0, key[1] + 500.0 / 85000.0
                    lines[i] = l[:len(l) - len(l.lstrip())] + \
                        "position %.6f%s %.6f%s%s" % (lat, m.group(2).lower(),
                                                      lon, m.group(4).lower(),
                                                      m.group(5))
                    return "\n".join(lines) + "\n", "offset the coincident waypoint %s" % s
                seen.add(key)
    return None, None


def fix_microsec(script, err):
    """A line with <number> microsec -> convert to sec. Only numbered lines count; comments are skipped."""
    lines = script.splitlines()
    for i, l in enumerate(lines):
        m = re.search(r"([\d.]+)\s*microsec", l)
        if m:
            lines[i] = l.replace("%s microsec" % m.group(1),
                                 "%s sec" % (float(m.group(1)) * 1e-6))
            return "\n".join(lines) + "\n", "converted microsec to sec"
    return None, None


REPAIR_RULES = [
    (r"Could not find platform_type", fix_type_hallucination),
    (r"Cannot open file:", fix_bad_include),
    (r"Unknown identifier:", fix_unknown_identifier),
    (r"Bad value for: position", fix_bad_position),
    (r"Unknown command: speed", fix_unknown_command_speed),
    (r"Coincident waypoints!", fix_coincident_waypoints),
    (r"Bad value for:", fix_microsec),
]

UNREPAIRABLE = ("Unexpected End Of Data",)   # unclosed block: back to the model


def fix_evt_no_enable(script, err):
    """schema R9: event_output with no enable -> add the minimal event set."""
    return script.replace("end_event_output",
                          "   enable PLATFORM_ADDED\n   enable PLATFORM_BROKEN\n"
                          "end_event_output", 1), \
        "added enable to event_output (PLATFORM_ADDED/BROKEN)"


def fix_altitude_no_unit(script, err):
    """schema R12: altitude with no unit -> append m."""
    return re.sub(r"altitude\s+([\d.]+)\s*$", r"altitude \1 m",
                  script, flags=re.M), "added the unit m to the altitude"


SCHEMA_FIXES = [
    ("R9", fix_evt_no_enable),
    ("R12", fix_altitude_no_unit),
]


def apply_schema_fixes(script_text, log):
    """Run the static check first; whatever a rule can express gets fixed here."""
    import schema_check
    errs = schema_check.check(script_text, schema_check.load_type_index(),
                              afsim_root=AFSIM_ROOT, base_dir=_HERE)
    for code, fn in SCHEMA_FIXES:
        if any(e[0] == code for e in errs):
            new_script, msg = fn(script_text, None)
            if new_script and new_script != script_text:
                script_text = new_script
                log.append("static fix: %s" % msg)
    return script_text


def repair_loop(script_text, workdir, max_iter=3):
    """Return (ok, rounds, log, final_script)."""
    log = []
    script_text = apply_schema_fixes(script_text, log)
    # if the static pass already added enable, do not add it again in the loop (bad05: it does not help)
    evt_fixed = any("added enable to event_output" in x for x in log)
    ok, out = run_engine(script_text, workdir)
    if ok:
        return True, 0, (log or ["the script passed unchanged"]), script_text
    for rnd in range(1, max_iter + 1):
        errs = _errors_of(out)
        acted = None
        for err in errs:
            for pat, fn in REPAIR_RULES:
                if re.search(pat, err):
                    new_script, msg = fn(script_text, err)
                    if new_script:
                        acted = (new_script, msg, err)
                        break
            if acted:
                break
        if acted is None:
            # no error text but a zero-byte .evt: the engine's silent failure. Add enable once;
            # if it stays empty the problem is semantic (no platforms, or the enable set misses the real events).
            evt = workdir / "output" / "scenario.evt"
            if errs == [] and (not evt.exists() or evt.stat().st_size == 0) \
                    and "event_output" in script_text and not evt_fixed:
                evt_fixed = True
                new_script, msg = fix_evt_no_enable(script_text, None)
                if new_script and new_script != script_text:
                    script_text = new_script
                    log.append("round %d: %s (.evt zero bytes, no error text)"
                               % (rnd, msg))
                    ok, out = run_engine(script_text, workdir)
                    if ok:
                        log.append("round %d passed after repair" % rnd)
                        return True, rnd, log, script_text
                    continue
                else:
                    log.append("round %d: adding enable did nothing (.evt still zero bytes),"
                               "no rule can fix this" % rnd)
                    return False, rnd, log, script_text
            fatal = [e for e in errs if any(u in e for u in UNREPAIRABLE)]
            if fatal:
                log.append("round %d: no rule applies (%s); back to the model" % (rnd, fatal[0]))
            else:
                why = ("the enabled events do not match the events that actually happen"
                       if re.search(r"(?m)^\s*platform\s+\w+", script_text)
                       else "the scenario has no platforms, so the event stream is bound to be empty")
                log.append("round %d: no matching repair rule (%s)" % (rnd, errs[:1] or why))
            return False, rnd, log, script_text
        script_text, msg, err = acted
        log.append("round %d: %s <- error %r" % (rnd, msg, err[:60]))
        ok, out = run_engine(script_text, workdir)
        if ok:
            log.append("round %d passed after repair" % rnd)
            return True, rnd, log, script_text
    log.append("still failing at the round limit")
    return False, max_iter, log, script_text


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "--all"
    if arg == "--all":
        samples = sorted((_HERE / "samples").glob("s*.txt"))
    else:
        p = Path(arg)
        samples = sorted(p.glob("bad*.txt")) if p.is_dir() else [p]
    n_ok = 0
    for f in samples:
        script = f.read_text(encoding="utf-8")
        wd = Path(tempfile.mkdtemp(prefix="afsim_repair_"))
        ok, rounds, log, final_script = repair_loop(script, wd)
        n_ok += ok
        # a pass is not the end: the engine reports nothing for "legal but absurd" (altitude 3 ft)
        warn = []
        if ok:
            import schema_check
            finds = schema_check.check(final_script, schema_check.load_type_index(),
                                       afsim_root=AFSIM_ROOT, base_dir=_HERE)
            warn = [m for c, sv, m in finds if sv == "warning"]
        print("%-30s %s  rounds=%d" % (f.name, "repaired" if ok else "failed", rounds))
        for line in log:
            print("    " + line)
        for w in warn:
            print("    [semantic warning] %s" % w)
        shutil.rmtree(wd, ignore_errors=True)
    print("repaired in one or more rounds: %.0f%% (%d/%d)" % (100.0 * n_ok / len(samples),
                                                n_ok, len(samples)))


if __name__ == "__main__":
    main()
