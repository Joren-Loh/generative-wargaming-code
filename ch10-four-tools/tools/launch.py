# -*- coding: utf-8 -*-
"""launch_afsim_tool: a GUI tool can be started, never waited on."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .guard import GuardError, safe_path

# only these five shipped executables, so model input never reaches a command line
TOOLS = {
    "wizard": "wizard.exe",
    "warlock": "warlock.exe",
    "mystic": "mystic.exe",
    "engage": "engage.exe",
    "sensor_plot": "sensor_plot.exe",
}


def launch_afsim_tool(config, args) -> dict:
    name = str(args.get("tool") or "").lower()
    if name not in TOOLS:
        return {"error": f"unknown tool: {name}", "allowed": sorted(TOOLS)}

    exe = Path(config["afsim_root"]) / "bin" / TOOLS[name]
    if not exe.exists():
        return {"error": f"executable not found: {exe}"}

    target = args.get("scenario_file")
    payload = {"tool": name, "exe": str(exe)}
    if target:
        try:
            payload["scenario_file"] = str(safe_path(target, config["roots"]))
        except GuardError as exc:
            return {"error": str(exc)}

    if args.get("dry_run", True):
        # a GUI holds its process open, so a self-test or an unattended call only locates it
        payload["dry_run"] = True
        payload["note"] = "resolved the executable path only, GUI not started; drop dry_run to actually open it"
        return payload

    cmd = [str(exe)] + ([payload["scenario_file"]] if target else [])
    proc = subprocess.Popen(cmd, cwd=str(exe.parent), close_fds=True)
    payload.update(dry_run=False, pid=proc.pid)
    return payload
