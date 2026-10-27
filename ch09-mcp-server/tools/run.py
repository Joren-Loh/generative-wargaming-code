# -*- coding: utf-8 -*-
"""run_mission: run mission.exe once and parse what it really said into structured facts."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .guard import clamp_timeout, safe_path

SEVERITY_RE = re.compile(r"^\*{5}\s+(ERROR|FATAL|WARNING):\s*(.+)$")
LOCATION_RE = re.compile(r"'([^']+)',\s*line\s+(\d+),\s*near column\s+(\d+)")
FILE_RE = re.compile(r"^\s+File:\s*(\S+)\s*$")
STAMP_RE = re.compile(r"^\d+(?::\d+){0,2}(?:\.\d+)?$")


def parse_diagnostics(text: str) -> list[dict]:
    """mission's error grammar: severity on one line, the location on the next."""
    lines = text.splitlines()
    out = []
    for i, line in enumerate(lines):
        match = SEVERITY_RE.match(line.strip())
        if not match:
            continue
        item = {"severity": match.group(1), "message": match.group(2).strip(),
                "file": None, "line": None, "column": None}
        for follow in lines[i + 1:i + 4]:
            loc = LOCATION_RE.search(follow)
            if loc:
                item.update(file=loc.group(1), line=int(loc.group(2)),
                            column=int(loc.group(3)))
                break
            anchor = FILE_RE.match(follow)
            if anchor:
                item["file"] = anchor.group(1)
                break
        out.append(item)
    return out


def evt_summary(output_dir: Path, stem: str) -> dict:
    files, events, categories = [], 0, {}
    if output_dir.is_dir():
        # only the .evt named after the entry file: the directory often holds the last run's leftovers, and mixing them miscounts
        for path in sorted(output_dir.glob(f"{stem}.evt")):
            size = path.stat().st_size
            files.append({"name": path.name, "bytes": size})
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line or line[0].isspace():
                    continue
                tokens = line.split()
                if len(tokens) < 2 or not STAMP_RE.match(tokens[0]):
                    continue
                events += 1
                categories[tokens[1]] = categories.get(tokens[1], 0) + 1
    return {"evt_files": files, "evt_events": events, "evt_categories": categories}


def run_mission(config, args) -> dict:
    scenario = safe_path(args["scenario"], config["roots"])
    root = config["afsim_root"]
    mission = Path(root) / "bin" / "mission.exe"
    if not mission.exists():
        return {"error": f"mission.exe not found: {mission}"}

    workdir = scenario.parent
    output_dir = workdir / "output"
    output_dir.mkdir(exist_ok=True)  # without this directory mission fails with InitializeError

    timeout = clamp_timeout(args.get("timeout_sec") or config["mission_timeout_sec"])
    timed_out = False
    try:
        proc = subprocess.run(
            [str(mission), scenario.name], cwd=str(workdir), timeout=timeout,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            stdin=subprocess.DEVNULL,
        )
        returncode, output = proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired as exc:
        timed_out, returncode = True, None
        output = (exc.stdout or "") if isinstance(exc.stdout, str) else ""

    diagnostics = parse_diagnostics(output)
    errors = [d for d in diagnostics if d["severity"] in ("ERROR", "FATAL")]
    located = [d for d in errors if d["file"]]
    complete = "Simulation complete" in output
    summary = evt_summary(output_dir, scenario.stem)

    activity = sum(n for k, n in summary["evt_categories"].items() if k != "PLATFORM_INITIALIZED")
    problems = []
    if timed_out:
        problems.append(f"mission timed out ({timeout:.0f} s)")
    if located:
        problems.append(f"{len(located)} errors carry a file location, so they are scenario defects")
    if returncode not in (0, None):
        problems.append(f"mission exited with code {returncode}")
    if not complete:
        problems.append("never reached 'Simulation complete'")
    if summary["evt_events"] == 0:
        problems.append("no .evt events, so nothing can be concluded")
    elif activity == 0:
        problems.append("it ran, but only PLATFORM_INITIALIZED: no detection, no track, no launch")
    if len(output) > config["max_output_chars"]:
        output = output[: config["max_output_chars"]] + "\n...<truncated>\n"

    payload = {
        "ok": not problems,
        "scenario": str(scenario),
        "returncode": returncode,
        "timed_out": timed_out,
        "simulation_complete": complete,
        "problems": problems,
        "errors": errors[:20],
        "error_count": len(errors),
        "outputs": summary,
        "log_tail": "\n".join(output.strip().splitlines()[-12:]),
    }
    if problems:
        # a failed verdict sets isError too: a client should not read ok alone
        payload["error"] = "run judged a failure: " + problems[0]
    return payload
