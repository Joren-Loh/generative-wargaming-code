# -*- coding: utf-8 -*-
"""Four tools: definitions for tools/list and routes for tools/call."""

from __future__ import annotations

from .analyze import analyze_run
from .launch import launch_afsim_tool
from .run import run_mission
from .types import afsim_types


class ToolError(Exception):
    """A business failure: answer with isError=true, never with a JSON-RPC error code."""


SPECS = [
    {
        "name": "afsim_types",
        "description": (
            "Look up a platform_type that really exists on this machine. The type namespace is closed,"
            "and an invented name is rejected outright, so the lookup comes first."
            "With no arguments, list every platform type in demos; pass name to see one type's parts."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "the platform_type to inspect, e.g. LTE_FIGHTER"},
                "keyword": {"type": "string", "description": "filter on a fragment of the name"},
                "armed_only": {"type": "boolean", "description": "list only types that carry a sensor or a weapon"},
                "limit": {"type": "integer", "description": "maximum rows returned; 40 by default"},
            },
        },
    },
    {
        "name": "run_mission",
        "description": (
            "Run mission.exe once and report what actually happened: exit code, errors located to"
            "file:line:column, whether Simulation complete was reached, and the .evt breakdown."
            "A run that places platforms and does nothing else counts as a failure, even at exit code 0."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "scenario": {"type": "string", "description": "absolute path of the scenario entry file"},
                "timeout_sec": {"type": "number", "description": "seconds before timeout, at most 600"},
            },
            "required": ["scenario"],
        },
    },
    {
        "name": "analyze_run",
        "description": (
            "Turn a finished .evt into a report: event counts, timeline, losses on each side,"
            "launches, hits and misses, time to first detection. An empty .evt gets a diagnosis, not invented KPIs."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "scenario_dir": {"type": "string", "description": "scenario directory; the tool finds output/*.evt itself"},
                "evt_path": {"type": "string", "description": "point straight at a .evt file"},
            },
        },
    },
    {
        "name": "launch_afsim_tool",
        "description": (
            "Start an AFSIM desktop tool (wizard / warlock / mystic / engage / sensor_plot)."
            "dry_run defaults on, so the call only locates the executable: a GUI holds its process open, and an unattended run should not pop windows."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "tool": {"type": "string",
                         "enum": ["wizard", "warlock", "mystic", "engage", "sensor_plot"]},
                "scenario_file": {"type": "string"},
                "dry_run": {"type": "boolean", "description": "true by default"},
            },
            "required": ["tool"],
        },
    },
]


def _require(config, args, key):
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ToolError(f"missing required argument: {key}")
    return value


def call_afsim_types(config, args):
    return afsim_types(config, args)


def call_run_mission(config, args):
    return run_mission(config, {"scenario": _require(config, args, "scenario"),
                                "timeout_sec": args.get("timeout_sec")})


def call_analyze_run(config, args):
    if not args.get("scenario_dir") and not args.get("evt_path"):
        raise ToolError("pass scenario_dir or evt_path")
    return analyze_run(config, args)


def call_launch(config, args):
    return launch_afsim_tool(config, {"tool": _require(config, args, "tool"),
                                      "scenario_file": args.get("scenario_file"),
                                      "dry_run": args.get("dry_run", True)})


ROUTER = {
    "afsim_types": call_afsim_types,
    "run_mission": call_run_mission,
    "analyze_run": call_analyze_run,
    "launch_afsim_tool": call_launch,
}
