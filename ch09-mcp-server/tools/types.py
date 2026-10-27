# -*- coding: utf-8 -*-
"""afsim_types: the type namespace is closed, so names are looked up, never invented."""

from __future__ import annotations

import re
from pathlib import Path

TYPE_RE = re.compile(r"^platform_type\s+(\S+)(?:\s+(\S+))?")
PART_RE = re.compile(r"^\s+(sensor|weapon|mover|processor|comm|filter)\s+(\S+)(?:\s+(\S+))?")


def _roots(config) -> list[Path]:
    return [Path(config["afsim_root"])] if config.get("afsim_root") else []


def build_index(config) -> dict:
    """Walk demos, collecting top-level platform_type declarations and the parts inside each platform."""
    roots = _roots(config)
    if not roots:
        return {"error": "AFSIM_ROOT is not configured, so no type catalogue can be built"}
    demos = roots[0] / "demos"
    if not demos.is_dir():
        return {"error": f"demos directory not found: {demos}"}

    index: dict[str, dict] = {}
    for path in demos.rglob("*.txt"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        current = None
        for line in text.splitlines():
            match = TYPE_RE.match(line)
            if match:
                current = match.group(1)
                index[current] = {
                    "base": match.group(2) or "WSF_PLATFORM",
                    "file": str(path.relative_to(roots[0])).replace("\\", "/"),
                    "parts": [],
                }
                continue
            if current and line.strip() == "end_platform_type":
                current = None
                continue
            if current:
                part = PART_RE.match(line)
                if part and part.group(3):
                    index[current]["parts"].append(
                        {"kind": part.group(1), "name": part.group(2), "type": part.group(3)}
                    )
    return index


def afsim_types(config, args) -> dict:
    index = build_index(config)
    if "error" in index:
        return index

    name = args.get("name")
    if name:
        entry = index.get(name)
        if entry is None:
            close = [k for k in index if name[:4].upper() in k][:8]
            return {"error": f"no platform_type {name} in demos", "did_you_mean": close}
        return {
            "name": name,
            "base": entry["base"],
            "include_path": entry["file"],
            "parts": entry["parts"],
            "armed": any(p["kind"] in ("sensor", "weapon") for p in entry["parts"]),
        }

    keyword = (args.get("keyword") or "").upper()
    rows = []
    for key, entry in index.items():
        if keyword and keyword not in key:
            continue
        parts = entry["parts"]
        armed = any(p["kind"] in ("sensor", "weapon") for p in parts)
        if args.get("armed_only") and not armed:
            continue
        rows.append(
            {
                "name": key,
                "base": entry["base"],
                "armed": armed,
                "components": len(parts),
            }
        )
    rows.sort(key=lambda row: (not row["armed"], row["name"]))
    limit = int(args.get("limit") or 40)
    return {
        "source": str(Path(config["afsim_root"]) / "demos"),
        "total_types": len(index),
        "matched": len(rows),
        "note": "only the platform_type declarations at the top level of demos are indexed; the built-in WSF_* classes live in the DLL, not in this table.",
        "types": rows[:limit],
    }

