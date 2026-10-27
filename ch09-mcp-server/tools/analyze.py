# -*- coding: utf-8 -*-
"""analyze_run: turn the .evt event stream into a report a person can read."""

from __future__ import annotations

import re
from pathlib import Path

from .guard import safe_path

STAMP_RE = re.compile(r"^\d+(?::\d+){0,2}(?:\.\d+)?$")
KV_RE = re.compile(r"([A-Za-z_]+):\s*([^\s\\]+)")


def parse_evt(path: Path) -> list[dict]:
    records = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line or line[0].isspace() or line.startswith("#"):
            continue
        tokens = line.rstrip("\\ ").split()
        if len(tokens) < 2 or not STAMP_RE.match(tokens[0]):
            continue
        kv = dict(KV_RE.findall(line))
        head = []
        for token in tokens[2:]:
            if token.endswith(":"):
                break
            head.append(token)
        records.append(
            {"t": float(tokens[0].replace(":", "")) if ":" not in tokens[0] else None,
             "raw_t": tokens[0], "event": tokens[1], "who": head, "kv": kv}
        )
    return records


def analyze_run(config, args) -> dict:
    if args.get("evt_path"):
        evt = safe_path(args["evt_path"], config["roots"])
    else:
        scenario_dir = safe_path(args["scenario_dir"], config["roots"])
        candidates = sorted((scenario_dir / "output").glob("*.evt"))
        if not candidates:
            return {"error": f"no .evt file under {scenario_dir / 'output'}",
                    "hint": "run run_mission first, or check where event_output's file points"}
        named = [p for p in candidates if p.stem == args.get("scenario")]
        evt = named[0] if named else max(candidates, key=lambda p: p.stat().st_size)

    if evt.stat().st_size == 0:
        return {"error": f"{evt.name} is zero bytes",
                "likely_cause": "event_output enables no events; AFSIM reports nothing and writes an empty file"}

    records = parse_evt(evt)
    counts: dict[str, int] = {}
    for rec in records:
        counts[rec["event"]] = counts.get(rec["event"], 0) + 1

    platforms, losses, expended = {}, {"blue": [], "red": []}, []
    fired, hits, missed = [], [], []
    detections = []
    times = [r["t"] for r in records if r["t"] is not None]

    for rec in records:
        event, kv, who = rec["event"], rec["kv"], rec["who"]
        if event in ("PLATFORM_INITIALIZED", "PLATFORM_ADDED") and who:
            platforms[who[0]] = {"type": kv.get("Type"), "side": kv.get("Side")}
        elif event == "WEAPON_FIRED" and len(who) >= 3:
            fired.append({"t": rec["t"], "shooter": who[0], "target": who[1], "weapon": who[2]})
        elif event == "WEAPON_HIT" and len(who) >= 3:
            hits.append({"t": rec["t"], "shooter": who[0], "target": who[1]})
        elif event == "WEAPON_MISSED" and len(who) >= 3:
            missed.append({"t": rec["t"], "shooter": who[0], "target": who[1]})
        elif event == "SENSOR_TRACK_INITIATED" and len(who) >= 2:
            detections.append({"t": rec["t"], "holder": who[0], "target": who[1]})
        elif event == "PLATFORM_BROKEN" and who:
            name, side = who[0], kv.get("Side")
            is_weapon = any(item["weapon"] == name for item in fired)
            if is_weapon:
                expended.append(name)
            elif side in losses:
                losses[side].append({"name": name, "type": kv.get("Type")})

    diagnostics = []
    if not records:
        diagnostics.append({"issue": "no_events", "detail": f"{evt.name} holds not one parsable event"})
    if not fired:
        diagnostics.append({"issue": "no_shots",
                            "detail": "zero launches throughout: check whether the weapon was added to the platform, and whether quantity is 0"})

    return {
        "evt": str(evt),
        "evt_bytes": evt.stat().st_size,
        "event_counts": counts,
        "timeline": {"first_sec": min(times) if times else None,
                     "last_sec": max(times) if times else None},
        "platforms": platforms,
        "engagements": {"fired": len(fired), "hits": len(hits), "missed": len(missed),
                        "shots": fired},
        "detections": {"count": len(detections),
                       "first_sec": detections[0]["t"] if detections else None},
        "losses": losses,
        "weapons_expended": expended,
        "kpi": {
            "kill_chain_closed": bool(hits),
            "blue_losses": len(losses["blue"]),
            "red_losses": len(losses["red"]),
            "time_to_first_shot_sec": fired[0]["t"] if fired else None,
        },
        "diagnostics": diagnostics,
    }
