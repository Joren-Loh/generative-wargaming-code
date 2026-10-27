# -*- coding: utf-8 -*-
"""
Schema check: the hallucination firewall. Purely static; no engine needed.

Rule list (R1-R15, the same family as the linter's L-rules, extended):
  R1  the platform_type a platform references must be defined in the demos type list or in this file (closed namespace)
  R2  an include_once path must really exist under the AFSIM root or the scenario directory (the include chain closes)
  R3  block pairing: platform / mover / sensor / route / event_output / script_variables
  R4  global script_variables must appear before every include_once
  R5  position coordinates must be paired, latitude first
  R6  unit blacklist: microsec, and other units that do not exist
  R7  a position line accepts no speed clause
  R8  route waypoints must not coincide numerically
  R9  event_output must enable at least one event explicitly
  R10 end_time must be present
  R11 altitude above 20000 m is suspect (wrong unit or magnitude)
  R12 an altitude number with no unit
  R13 altitude below 100 ft inside a platform instance: ground level, magnitude suspect (warning)
  R14 a number carrying a thousands separator
  R15 a platform instance with no side (silent neutral: no error, no engagement)

Usage: python schema_check.py <file.txt | dir>    a directory gives batch totals
Exit code: 1 if anything at error level was found, 0 otherwise.
"""
import difflib
import json
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_KNOWLEDGE = _HERE / "knowledge"
_COORD = re.compile(r"[-\d:.]+[nsew]\b", re.I)


def load_type_index():
    pt = json.loads((_KNOWLEDGE / "platform_types.json").read_text(encoding="utf-8"))
    return set(pt)


def check(script, type_index, afsim_root=None, base_dir=None):
    """Return [(code, severity, message), ...]; severity is error or warning."""
    out = []
    # strip comment lines first: example words inside comments (enable, event_output) disturb the rules
    script = re.sub(r"(?m)^\s*#.*$", "", script)
    defined = set(re.findall(r"platform_type\s+(\w+)\s+WSF_\w+", script))
    index = type_index | defined

    # R1 closed namespace, with the nearest candidates (WSF_PLATFORM is built in, so it passes)
    for name in re.findall(r"^\s*platform\s+\w+\s+(\w+)", script, re.M):
        if name not in index and name.upper() != "WSF_PLATFORM":
            near = difflib.get_close_matches(name, type_index, n=3, cutoff=0.6)
            out.append(("R1", "error", "platform_type %r does not exist; candidates: %s"
                        % (name, ", ".join(near) or "none")))

    # R2 the include chain closes
    for inc in re.findall(r"include_once\s+(\S+)", script):
        cands = [Path(afsim_root) / inc] if afsim_root else []
        if base_dir:
            cands.append(Path(base_dir) / inc)
        if cands and not any(c.exists() for c in cands):
            out.append(("R2", "error", "include path does not exist: %s" % inc))

    # R3 block pairing, by counting
    for blk in ("platform_type", "platform", "mover", "sensor", "route",
                "event_output", "script_variables"):
        opens = len(re.findall(r"^\s*%s(\s|$)" % blk, script, re.M))
        closes = len(re.findall(r"^\s*end_%s\s*$" % blk, script, re.M))
        if opens > closes:
            out.append(("R3", "error", "unclosed block: %s (%d open / %d close)" % (blk, opens, closes)))

    # R4 where the global script_variables sit
    inc_pos = [m.start() for m in re.finditer(r"include_once", script)]
    for m in re.finditer(r"^script_variables", script, re.M):
        if inc_pos and m.start() > inc_pos[0]:
            out.append(("R4", "error", "global script_variables come after an include_once (Unknown identifier)"))

    # R5 coordinates paired, latitude first
    for line in script.splitlines():
        s = line.strip()
        if s.startswith("position "):
            coords = _COORD.findall(s)
            if len(coords) < 2:
                out.append(("R5", "error", "coordinates are not paired (%d of them): %s" % (len(coords), s)))
            elif len(coords) >= 2 and coords[0][-1].lower() in "ew":
                out.append(("R5", "error", "latitude is not first (longitude was written first): %s" % s))

    # R6 unit blacklist / R14 thousands separator
    for bad in ("microsec", "millisec"):
        if re.search(r"\d\s*%s\b" % bad, script):
            out.append(("R6", "error", "unit %s does not exist (write 1.0e-6 sec)" % bad))
    if re.search(r"\d,\d{3}", script):
        out.append(("R14", "error", "number carries a thousands separator (e.g. 30,000)"))

    # R7 a position line carrying speed (legal on a route waypoint)
    outside_route = re.sub(r"route.*?end_route", "", script, flags=re.S)
    for line in outside_route.splitlines():
        s = line.strip()
        if s.startswith("position ") and re.search(r"\bspeed\b", s):
            out.append(("R7", "error", "position line carries a speed clause: %s" % s))

    # R8 coincident waypoints (DMS coordinates included)
    for route in re.findall(r"route(.*?)end_route", script, re.S):
        pts = re.findall(r"position\s+([\d:.]+)[nNsS]\s+([\d:.]+)[eEwW]", route)
        if pts and len(pts) != len(set(pts)):
            out.append(("R8", "error", "route has coincident waypoints (Coincident waypoints!)"))

    # R9 event_output with no enable
    for blk in re.findall(r"event_output(.*?)end_event_output", script, re.S):
        if "enable" not in blk:
            out.append(("R9", "error", "event_output enables nothing (the .evt will be zero bytes)"))

    # R10 end_time / R12 no unit / R11 too high / R13 too low (inside a platform instance only)
    if "end_time" not in script:
        out.append(("R10", "warning", "no end_time (the default run is 60 seconds)"))
    plat_blocks = re.findall(r"(?ms)^\s*platform\s+\w+.*?^\s*end_platform", script)
    for blk in plat_blocks:
        if not re.search(r"^\s*side\s+\w+", blk, re.M):
            name = re.search(r"platform\s+(\w+)", blk).group(1)
            out.append(("R15", "error", "platform %s has no side (silent neutral)" % name))
        for m in re.finditer(r"altitude\s+([\d.]+)\s*(m|ft|kft|nmi)?", blk):
            val, unit = float(m.group(1)), m.group(2)
            if unit is None:
                out.append(("R12", "error", "altitude has no unit: altitude %g" % val))
            else:
                meters = val * {"m": 1.0, "ft": 0.3048, "kft": 304.8, "nmi": 1852.0}[unit]
                if meters > 20000.0:
                    out.append(("R11", "error", "altitude suspect (>20 km): %g %s" % (val, unit)))
                elif unit == "ft" and val < 100.0:
                    out.append(("R13", "warning", "altitude too low (ground level, magnitude suspect): %g ft" % val))
    return out


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not path:
        print("usage: python schema_check.py <scenario.txt | dir>")
        return 2
    afsim_root = _HERE.parent.parent.parent / "afsim-2.9.0"
    files = sorted(path.glob("*.txt")) if path.is_dir() else [path]
    n_hit, n_rule = 0, {}
    for f in files:
        finds = check(f.read_text(encoding="utf-8"), load_type_index(),
                      afsim_root=afsim_root, base_dir=f.parent)
        errs = [x for x in finds if x[1] == "error"]
        n_hit += bool(errs)
        for code, sev, msg in finds:
            n_rule[code] = n_rule.get(code, 0) + 1
            print("%-14s %s %-4s %s" % (f.name, sev, code, msg))
    if path.is_dir():
        print("---- %d/%d files hit an error; rule hits: %s"
              % (n_hit, len(files), dict(sorted(n_rule.items()))))
    return 1 if n_hit else 0


if __name__ == "__main__":
    sys.exit(main())
