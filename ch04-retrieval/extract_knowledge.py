# -*- coding: utf-8 -*-
"""
Extract a "locally quotable" knowledge base from demos.

Outputs, under knowledge/:
  platform_types.json   every platform_type the demos define (name, side hint, source file)
  syntax_snippets.md    syntax fragments, hand-picked, for the retriever
  error_cases.json      error cases: verbatim message -> class -> repair hint

Usage: python extract_knowledge.py [--afsim-root ../../..../afsim-2.9.0]
"""

import argparse
import json
import re
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_KNOWLEDGE = _HERE / "knowledge"

_PLATFORM_TYPE_RE = re.compile(r"^\s*platform_type\s+(\w+)\s+WSF_PLATFORM", re.M)
_INCLUDE_RE = re.compile(r"^\s*include_once\s+(\S+)", re.M)


def extract_platform_types(afsim_root):
    """Walk every .txt under demos and models, collecting platform_type definitions."""
    types = {}
    root = Path(afsim_root)
    for sub in ("demos", "models"):
        base = root / sub
        if not base.exists():
            continue
        for f in base.rglob("*.txt"):
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for m in _PLATFORM_TYPE_RE.finditer(text):
                name = m.group(1)
                if name not in types:
                    types[name] = {
                        "name": name,
                        "defined_in": str(f.relative_to(root)).replace("\\", "/"),
                    }
    return types


def extract_includes(afsim_root):
    """include_once targets that appear in demos, i.e. paths that work on this machine."""
    incs = set()
    root = Path(afsim_root)
    for f in (root / "demos").rglob("*.txt"):
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in _INCLUDE_RE.finditer(text):
            incs.add(m.group(1))
    return sorted(incs)


ERROR_CASES = [
    {"error": "Could not find platform_type BLUE_STEALTH_FIGHTER_X", "type": "type-name hallucination",
     "hint": "the platform references a type that does not exist; use one from the knowledge base, or define it in this file"},
    {"error": "Cannot open file: models/stealth_fighter.txt", "type": "wrong include path",
     "hint": "the include_once path does not exist on this machine; delete it or use a path the demos use"},
    {"error": "Unknown identifier: 'gMystery'", "type": "undeclared variable",
     "hint": "global script_variables must precede every include_once, and must be declared before use"},
    {"error": "Bad value for: position", "type": "reversed coordinates",
     "hint": "position takes latitude, then longitude, then an optional altitude"},
    {"error": "Coincident waypoints!", "type": "coincident waypoints",
     "hint": "route contains numerically duplicated waypoints; dedupe them or offset one slightly"},
    {"error": "Expected value '0' to be > 0", "type": "illegal time value",
     "hint": "execute at_time must be greater than 0; change 0.0 to 0.1 or 1.0"},
    {"error": "Bad value for: update_interval", "type": "illegal unit",
     "hint": "microsec is not a unit here; write 1.0e-6 sec instead"},
    {"error": "Unknown command: speed", "type": "clause in the wrong place",
     "hint": "speed belongs to a route waypoint; a position line inside a platform block does not accept it"},
    {"error": "Unexpected End Of Data", "type": "unclosed block",
     "hint": "a block is missing its end_xxx; check the pairing of platform, mover, route and so on, level by level"},
    {"error": ".evt is zero bytes and nothing is reported", "type": "event_output without enable",
     "hint": "every event you need must be enabled explicitly inside the event_output block"},
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--afsim-root", default=str(_HERE.parent.parent.parent / "afsim-2.9.0"))
    args = ap.parse_args()
    _KNOWLEDGE.mkdir(parents=True, exist_ok=True)
    types = extract_platform_types(args.afsim_root)
    (_KNOWLEDGE / "platform_types.json").write_text(
        json.dumps(types, ensure_ascii=False, indent=1), encoding="utf-8")
    incs = extract_includes(args.afsim_root)
    (_KNOWLEDGE / "known_includes.json").write_text(
        json.dumps(incs, ensure_ascii=False, indent=1), encoding="utf-8")
    (_KNOWLEDGE / "error_cases.json").write_text(
        json.dumps(ERROR_CASES, ensure_ascii=False, indent=1), encoding="utf-8")
    print("platform_type total:", len(types))
    print("valid include paths:", len(incs))


if __name__ == "__main__":
    main()
