#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Static scenario checker, six rules (L01-L06).

On top of the four-rule version, this adds:
  L05  reversed coordinates -- the first token carries e/w, the second n/s;
  L06  a position line carrying speed inside a platform block -- speed belongs to
       a route waypoint, so writing it there earns: Unknown command: speed.

Usage:
  python scenario_lint.py scenario.txt          # one file, includes expanded
  python scenario_lint.py <dir>                 # every .txt below a directory
Exit code: 1 if anything was reported, 0 if clean. Standard library only.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

COMMENT = re.compile(r"(#|//).*$")
# coordinate token: 0.5n / 30:00:00.00n / 118.0e / 01:47:21.156w
LAT_RE = re.compile(r"^\d+(:\d+)*(\.\d+)?[ns]$", re.IGNORECASE)
LON_RE = re.compile(r"^\d+(:\d+)*(\.\d+)?[ew]$", re.IGNORECASE)


def strip_comment(line: str) -> str:
    return COMMENT.sub("", line).strip()


def iter_statements(text: str):
    for lineno, raw in enumerate(text.splitlines(), 1):
        s = strip_comment(raw)
        if s:
            yield lineno, s


def check_file(path: Path, issues: list, seen_includes: set | None = None,
               roots: list | None = None) -> None:
    seen_includes = seen_includes if seen_includes is not None else set()
    roots = roots if roots is not None else [path.parent]
    if path in seen_includes:
        return
    seen_includes.add(path)
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as e:
        issues.append(("ERR", path, 0, f"cannot read: {e}"))
        return

    lines = list(iter_statements(text))

    # collect define_path_variable and file_path (the include search path)
    path_vars: dict[str, str] = {}
    for lineno, s in lines:
        head = s.split()
        if head[0].lower() == "define_path_variable" and len(head) >= 3:
            path_vars[head[1]] = head[2]
        if head[0].lower() == "file_path" and len(head) >= 2:
            d = (path.parent / head[1]).resolve()
            if d.is_dir() and d not in roots:
                roots.append(d)

    def expand(p: str) -> str:
        for k, v in path_vars.items():
            p = p.replace("${" + k + "}", v)
        return p

    includes: list[tuple[int, str]] = []
    for lineno, s in lines:
        kw = s.split()[0].lower()
        if kw in ("include", "include_once") and len(s.split()) > 1:
            includes.append((lineno, s.split()[1]))

    # ---- block splitting (platform / route / event_output; single-line platform too) ----
    blocks = []
    cur = None
    for lineno, s in lines:
        kw = s.split()[0].lower()
        if cur is None:
            if kw in ("platform", "route", "event_output"):
                if kw == "platform" and s.lower().endswith("end_platform"):
                    blocks.append((kw, lineno, lineno, []))
                    continue
                cur = [kw, lineno, []]
        else:
            if kw == "end_" + cur[0]:
                blocks.append((cur[0], cur[1], lineno, cur[2]))
                cur = None
            else:
                cur[2].append((lineno, s))

    # pull nested route blocks out of a platform block and check them separately
    # (a position carrying speed is legal inside route, illegal inside platform)
    nested_routes = []
    for kind, l0, l1, body in blocks:
        if kind != "platform":
            continue
        rcur = None
        outside = []
        for ln, s in body:
            kw = s.split()[0].lower()
            if rcur is None:
                if kw == "route":
                    rcur = [ln, []]
                    continue
                outside.append((ln, s))
            else:
                if kw == "end_route":
                    nested_routes.append(("route", rcur[0], ln, rcur[1]))
                    rcur = None
                else:
                    rcur[1].append((ln, s))
        body[:] = outside          # direct platform clauses only, no nested route
    blocks.extend(nested_routes)

    # ---- L01 platform block with no side ----
    for kind, l0, l1, body in blocks:
        if kind == "platform" and not any(
                t.split()[0].lower() == "side" for _, t in body):
            issues.append(("L01", path, l0,
                           "platform block has no side (the instance joins as a neutral; detection and engagement never happen)"))

    # ---- L02 event_output with no enable ----
    for kind, l0, l1, body in blocks:
        if kind == "event_output" and not any(
                t.split()[0].lower() in ("enable", "disable") for _, t in body):
            issues.append(("L02", path, l0,
                           "event_output has neither enable nor disable; the .evt file will be zero bytes"))

    # ---- L03 duplicate waypoints (identical adjacent clause, matching the engine) ----
    for kind, l0, l1, body in blocks:
        if kind != "route":
            continue
        prev = None
        for ln, s in body:
            tok = s.split()
            if tok[0].lower() not in ("position", "offboard_pnt"):
                continue
            key = " ".join(t.lower() for t in tok)
            if key == prev:
                issues.append(("L03", path, ln,
                               f"waypoint duplicates line {ln - 1} exactly (Coincident waypoints!)"))
            prev = key

    # ---- L05 reversed coordinates / L06 position carrying speed, inside a platform ----
    for kind, l0, l1, body in blocks:
        if kind != "platform":
            continue
        for ln, s in body:
            tok = s.split()
            if tok[0].lower() != "position":
                continue
            if len(tok) >= 2 and LON_RE.match(tok[1]) and len(tok) >= 3 \
                    and LAT_RE.match(tok[2]):
                issues.append(("L05", path, ln,
                               f"suspected reversed coordinates: '{tok[1]} {tok[2]}' (expected latitude longitude)"))
            if any(t.lower() == "speed" for t in tok):
                issues.append(("L06", path, ln,
                               "position line carrying speed: speed belongs to a route waypoint, and a platform"
                               " position line reports: Unknown command: speed"))

    # ---- L05 also applies inside a route block (first coordinate is latitude) ----
    for kind, l0, l1, body in blocks:
        if kind != "route":
            continue
        for ln, s in body:
            tok = s.split()
            if tok and tok[0].lower() == "position" and len(tok) >= 3 \
                    and LON_RE.match(tok[1]) and LAT_RE.match(tok[2]):
                issues.append(("L05", path, ln,
                               f"suspected reversed coordinates: '{tok[1]} {tok[2]}' (expected latitude longitude)"))

    # ---- expand includes ----
    for ln, inc in includes:
        expanded = expand(inc)
        target = None
        for base in [path.parent] + roots:
            cand = (base / expanded).resolve()
            if cand.exists():
                target = cand
                break
        if target is not None:
            check_file(target, issues, seen_includes, roots)
        elif "$" in expanded:
            pass
        else:
            issues.append(("L04", path, ln, f"include target not found: {inc}"))


def collect_file_path_roots(target: Path) -> list:
    """Pre-scan file_path directives (the entry file supplies search paths for every include)."""
    roots = []
    try:
        text = target.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return roots
    for raw in text.splitlines():
        s = strip_comment(raw)
        if not s:
            continue
        head = s.split()
        if head[0].lower() == "file_path" and len(head) >= 2:
            d = (target.parent / head[1]).resolve()
            if d.is_dir() and d not in roots:
                roots.append(d)
    return roots


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    targets: list[Path] = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            targets.extend(sorted(p.rglob("*.txt")))
        else:
            targets.append(p)

    # file_path is an entry-file-level search path: collect it from every target first,
    # so an include anywhere can use the paths the entry file declared, like the engine does
    global_roots: list = []
    for t in targets:
        for d in collect_file_path_roots(t):
            if d not in global_roots:
                global_roots.append(d)

    issues: list = []
    seen_files: set = set()
    for t in targets:
        check_file(t, issues, seen_files, [t.parent] + global_roots)

    # a file can be reached from several targets; dedupe by (code, file, line, message)
    uniq = []
    seen_issues: set = set()
    for it in issues:
        k = (it[0], str(it[1]), it[2], it[3])
        if k not in seen_issues:
            seen_issues.add(k)
            uniq.append(it)
    issues = uniq

    if not issues:
        print(f"checked {len(seen_files)} files: no problems found")
        return 0

    order = {f"L0{i}": i - 1 for i in range(1, 7)}
    order["ERR"] = 9
    issues.sort(key=lambda x: (order.get(x[0], 9), str(x[1]), x[2]))
    for code, path, ln, msg in issues:
        print(f"[{code}] {path}:{ln}  {msg}")
    n = len(issues)
    print(f"\n{n} problems across {len({str(i[1]) for i in issues})} files")
    return 1


if __name__ == "__main__":
    sys.exit(main())
