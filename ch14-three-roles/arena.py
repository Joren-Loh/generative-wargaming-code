# -*- coding: utf-8 -*-
"""arena.py -- one game, end to end: skill -> scenario -> mission.exe -> event stream -> verdict.

Scheduling only, no physics: who lives and who dies is decided by the engine's PLATFORM_BROKEN,
and this file does nothing but read the event stream into counts.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path

import os

BASE = Path(__file__).resolve().parent
# AFSIM root: environment variable, then ../afsim-2.9.0 in this repository, then the usual install paths
ROOT = Path(os.environ.get("AFSIM_ROOT") or Path(__file__).resolve().parents[3] / "afsim-2.9.0")
if not ROOT.exists():
    ROOT = Path("D:/AFSIM/afsim-2.9.0")
MISSION = ROOT / "bin" / "mission.exe"
TEMPLATE = (BASE / "scenario_template.txt").read_text(encoding="utf-8")
STAMP_RE = re.compile(r"^\d+(?::\d+){0,2}(?:\.\d+)?$")
KV_RE = re.compile(r"([A-Za-z_]+):\s*([^\s\\]+)")

DEFAULT_PARAMS = {
    "alt_m": 8000,
    "speed_ms": 250,
    "fire_range_km": 12,
    "quantity": 2,
    "salvo": 1,
    "offset_deg": 0.0,
}


def load_skills() -> dict[str, dict]:
    skills = {}
    for path in sorted((BASE / "skills").glob("*.json")):
        skill = json.loads(path.read_text(encoding="utf-8"))
        merged = dict(DEFAULT_PARAMS)
        merged.update(skill.get("params", {}))
        skill["params"] = merged
        skills[skill["id"]] = skill
    return skills


def jitter(skill: dict, seed: int, tag: str) -> dict:
    """The seed drives the initial geometry jitter only and never enters the engine's decisions: that is what makes a re-run reproducible."""
    salt = sum(ord(c) for c in tag)
    p = dict(skill["params"])
    p["alt_m"] += ((seed * 37 + salt) % 601) - 300            # ±300 m
    p["offset_deg"] += (((seed * 53 + salt) % 21) - 10) / 1000  # ±0.01°
    p["speed_ms"] += ((seed * 29 + salt) % 11) - 5             # ±5 m/s
    return p


def render(blue: dict, red: dict, seed: int) -> str:
    text = TEMPLATE.replace("{{SEED}}", str(seed))
    base_lat, base_lon = 39.0, 116.0
    text = text.replace("{{BLUE_LAT}}", f"{base_lat:.4f}n")
    text = text.replace("{{BLUE_END_LAT}}", f"{base_lat + 0.3:.4f}n")
    text = text.replace("{{BLUE_LON}}", f"{base_lon + blue['offset_deg']:.4f}e")
    text = text.replace("{{RED_LAT}}", f"{base_lat + 0.3333:.4f}n")
    text = text.replace("{{RED_END_LAT}}", f"{base_lat + 0.0333:.4f}n")
    text = text.replace("{{RED_LON}}", f"{base_lon + red['offset_deg']:.4f}e")
    for side, params in (("BLUE", blue), ("RED", red)):
        text = text.replace(f"{{{{{side}_ALT}}}}", f"{int(params['alt_m'])} m")
        text = text.replace(f"{{{{{side}_SPEED}}}}", f"{int(params['speed_ms'])} m/s")
        text = text.replace(f"{{{{{side}_FIRE_RANGE}}}}", f"{params['fire_range_km'] * 1000:.0f}.0")
        text = text.replace(f"{{{{{side}_SALVO}}}}", str(int(params["salvo"])))
        text = text.replace(f"{{{{{side}_QUANTITY}}}}", str(max(int(params["quantity"]), int(params["salvo"]))))
    left = re.findall(r"\{\{[A-Z_]+\}\}", text)
    if left:
        raise ValueError(f"template still has unsubstituted placeholders: {sorted(set(left))}")
    return text


def parse_evt(path: Path) -> dict:
    """Event stream -> counts. Every criterion comes from an event; nothing is inferred from a platform being called something like sam."""
    sides, broken, shots, hits, detections = {}, [], {"blue": 0, "red": 0}, {"blue": 0, "red": 0}, {}
    first_shot = {"blue": None, "red": None}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line or line[0].isspace():
            continue
        tokens = line.rstrip("\\ ").split()
        if len(tokens) < 2 or not STAMP_RE.match(tokens[0]):
            continue
        t, event = float(tokens[0]), tokens[1]
        kv = dict(KV_RE.findall(line))
        head = []
        for token in tokens[2:]:
            if token.endswith(":"):
                break
            head.append(token)
        if event in ("PLATFORM_INITIALIZED", "PLATFORM_ADDED") and head:
            sides[head[0]] = kv.get("Side")
        elif event == "PLATFORM_BROKEN" and head and kv.get("Type") == "DUEL_FIGHTER":
            broken.append(kv.get("Side"))
        elif event == "WEAPON_FIRED" and head:
            side = sides.get(head[0], "blue")
            shots[side] += 1
            if first_shot[side] is None:
                first_shot[side] = t
        elif event == "WEAPON_HIT" and head:
            hits[sides.get(head[0], "blue")] += 1
        elif event == "SENSOR_TRACK_INITIATED" and head:
            detections.setdefault(head[0], t)
    return {
        "blue_losses": broken.count("blue"),
        "red_losses": broken.count("red"),
        "shots": shots,
        "hits": hits,
        "first_shot": first_shot,
        "first_detect": detections,
        "broken_sides": broken,
    }


def decide(evt: dict) -> tuple[str, str]:
    """The verdict order is fixed: killed > hit > first shot > first detection > draw."""
    if evt["red_losses"] != evt["blue_losses"]:
        winner = "blue" if evt["red_losses"] > evt["blue_losses"] else "red"
        return winner, "kills"
    if evt["hits"]["blue"] != evt["hits"]["red"]:
        winner = "blue" if evt["hits"]["blue"] > evt["hits"]["red"] else "red"
        return winner, "hits"
    fb, fr = evt["first_shot"]["blue"], evt["first_shot"]["red"]
    if fb is not None and fr is not None and fb != fr:
        return ("blue" if fb < fr else "red"), "first_shot"
    return "draw", "tie"


def play(blue_skill: dict, red_skill: dict, seed: int, tag: str = "", timeout: int = 120,
         workdir: Path | None = None) -> dict:
    """Play one game. workdir exists for parallelism: one directory per process, or scenario.txt overwrites itself."""
    work = Path(workdir) if workdir else BASE
    work.mkdir(parents=True, exist_ok=True)
    if work != BASE:                      # the scenario's includes are relative to cwd, so the model files move with it
        shutil.copytree(BASE / "models", work / "models", dirs_exist_ok=True)
    blue = jitter(blue_skill, seed, blue_skill["id"])
    red = jitter(red_skill, seed, red_skill["id"])
    scenario = work / "scenario.txt"
    scenario.write_text(render(blue, red, seed), encoding="utf-8")
    (work / "output").mkdir(exist_ok=True)

    started = time.perf_counter()
    proc = subprocess.run([str(MISSION), "scenario.txt"], cwd=str(work), timeout=timeout,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    elapsed = time.perf_counter() - started

    evt_path = work / "output" / "scenario.evt"
    record = {
        "tag": tag, "seed": seed,
        "blue": blue_skill["id"], "red": red_skill["id"],
        "blue_params": blue, "red_params": red,
        "returncode": proc.returncode,
        "complete": "Simulation complete" in (proc.stdout or ""),
        "elapsed_ms": round(elapsed * 1000),
        "evt_events": 0, "winner": None, "reason": "", "error": "",
    }
    if not evt_path.exists() or evt_path.stat().st_size == 0:
        record["error"] = "no .evt produced"
        return record

    evt = parse_evt(evt_path)
    record["evt_events"] = len(evt_path.read_text(encoding="utf-8", errors="replace").splitlines())
    record.update(evt)
    winner, reason = decide(evt)
    record["winner"], record["reason"] = winner, reason
    return record


def archive(record: dict) -> Path:
    path = BASE / "runs" / f"{record['tag'] or 'game'}_{record['seed']}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    skills = load_skills()
    print(f"installed {len(skills)} skills: {', '.join(skills)}")
    print(f"mission.exe: {MISSION} ({'present' if MISSION.exists() else 'missing'})")
    one = play(skills["rush_low"], skills["standoff_high"], 1001, tag="smoke")
    print(json.dumps(one, ensure_ascii=False, indent=2)[:1200])
