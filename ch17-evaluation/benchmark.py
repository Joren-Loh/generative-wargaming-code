"""An air-combat agent benchmark: scheduling plus statistics.

    python benchmark.py --episodes 8            # 3 agents x 2 tasks x 8 episodes
    python benchmark.py --agents rule --episodes 4

Design notes:
  * each (task, agent, seed) is one episode and maps to exactly one AFSIM process;
  * an agent acts only inside decide(), and produces scenario parameters, never touching the simulation;
  * all randomness comes from the seed plus the agent's own RNG, so a seed reproduces;
  * a failed episode still lands in the CSV with status=failed: it is never dropped silently.
"""

import argparse
import csv
import importlib
import json
import os
import random
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "agents"))

AGENT_FILES = {
    "rule": ("rule_agent", "RuleAgent"),
    "random": ("random_agent", "RandomAgent"),
    "scripted": ("scripted_agent", "ScriptedAgent"),
}
EVT_HEAD = re.compile(r"^([0-9.]+)\s+([A-Z_]+)\s+(.*)$")


def afsim_root():
    cand = [os.environ.get("AFSIM_ROOT")]
    cfg = os.path.join(ROOT, "config.json")
    if os.path.exists(cfg):
        cand.append(json.load(open(cfg, encoding="utf-8")).get("afsim_root"))
    cand.append(os.path.join(ROOT, "..", "..", "..", "afsim-2.9.0"))
    for c in cand:
        if c and os.path.isfile(os.path.join(c, "bin", "mission.exe")):
            return os.path.abspath(c)
    raise SystemExit("mission.exe not found; set AFSIM_ROOT")


def make_agent(name, seed):
    mod, cls = AGENT_FILES[name]
    obj = getattr(importlib.import_module(mod), cls)
    return obj(seed=seed) if name == "random" else obj()


def lon_of(base_lon, delta_km):
    """Turn "delta_km to the east" into AFSIM's deg:min:sec{E/W} form.

    Note that "-01.598" will not do: AFSIM's position accepts only the hemisphere-suffixed form,
    and a minus sign is a format error (Bad value for: position).
    """
    lon = base_lon + delta_km / 111.32
    hemi = "e" if lon >= 0 else "w"
    lon = abs(lon)
    d = int(lon)
    m = int((lon - d) * 60)
    s = ((lon - d) * 60 - m) * 60
    return "%02d:%02d:%05.2f%s" % (d, m, s, hemi)


def render(task, obs, action, seed, end_s):
    tpl = open(os.path.join(ROOT, "scenario_template.txt"), encoding="utf-8").read()
    half = obs["separation_m"] / 2000.0
    sub = {
        "SEED": seed, "END": end_s,
        "BLUE_FR": action["fire_range_m"], "RED_FR": task["red"]["fire_range_m"],
        "BLUE_SPD": action["speed_mps"], "RED_SPD": task["red"]["speed_mps"],
        "BLUE_ALT": obs["blue_alt_m"], "RED_ALT": obs["red_alt_m"],
        "BLUE_LON": lon_of(-1.33333, -half), "RED_LON": lon_of(-1.33333, half),
    }
    for k, v in sub.items():
        tpl = tpl.replace("__%s__" % k, str(v))
    assert "__" not in tpl, "the template still holds a placeholder"
    return tpl


def parse_evt(path):
    """Pull KPIs out of the .evt. Only a FIGHTER's PLATFORM_BROKEN counts, so a missile is not scored as a loss."""
    if not os.path.exists(path):
        return None
    blue_kill = blue_dead = shots_blue = shots_red = hits_blue = 0
    first_shot = None
    last_t = 0.0
    for line in open(path, encoding="utf-8", errors="ignore"):
        m = EVT_HEAD.match(line)
        if not m:
            continue
        t, kind, rest = float(m.group(1)), m.group(2), m.group(3).split()
        last_t = max(last_t, t)
        if kind == "PLATFORM_BROKEN" and "Type: FIGHTER" in line:
            if rest[0] == "red_1":
                blue_kill = 1
            elif rest[0] == "blue_1":
                blue_dead = 1
        elif kind == "WEAPON_FIRED" and rest[0] in ("blue_1", "red_1"):
            if rest[0] == "blue_1":
                shots_blue += 1
                first_shot = t if first_shot is None else min(first_shot, t)
            else:
                shots_red += 1
        elif kind == "WEAPON_HIT" and rest[0] == "blue_1":
            hits_blue += 1
    outcome = ("blue" if blue_kill and not blue_dead else
               "red" if blue_dead and not blue_kill else "draw")
    score = 1 if outcome == "blue" else (-1 if outcome == "red" else 0)
    return {"outcome": outcome, "score": score, "blue_kill": blue_kill,
            "blue_dead": blue_dead, "shots_blue": shots_blue, "shots_red": shots_red,
            "hits_blue": hits_blue, "first_shot_s": first_shot, "end_s": round(last_t, 2)}


def run_one(exe, task, agent, seed, episodes_dir, end_s):
    task_id = task["id"]
    run_dir = os.path.join(episodes_dir, "%s__%s__%d" % (task_id, agent.name, seed))
    os.makedirs(os.path.join(run_dir, "output"), exist_ok=True)

    rng = random.Random(seed * 7919 + 17)
    sep = rng.uniform(*task["sample"]["separation_km"]) * 1000.0
    obs = {
        "task_id": task_id, "separation_m": sep,
        "blue_alt_m": rng.uniform(*task["sample"]["blue_alt_m"]),
        "red_alt_m": rng.uniform(*task["sample"]["red_alt_m"]),
        "red_speed_mps": task["red"]["speed_mps"],
        "red_fire_range_m": task["red"]["fire_range_m"],
        "max_tof_s": 30.0, "seed": seed,
    }
    obs["blue_alt_m"] = round(obs["blue_alt_m"], -1)
    obs["red_alt_m"] = round(obs["red_alt_m"], -1)

    t0 = time.perf_counter()
    action = agent.decide(dict(obs))
    decision_ms = (time.perf_counter() - t0) * 1000.0

    with open(os.path.join(run_dir, "scenario.txt"), "w", encoding="utf-8") as f:
        f.write(render(task, obs, action, seed, end_s))
    proc = subprocess.run([exe, "scenario.txt"], cwd=run_dir,
                          capture_output=True, text=True, errors="ignore")
    ok = proc.returncode == 0 and "Simulation complete" in (proc.stdout or "")
    with open(os.path.join(run_dir, "mission.out"), "w", encoding="utf-8") as f:
        f.write(proc.stdout or "")
    kpi = parse_evt(os.path.join(run_dir, "output", "scenario.evt")) or {}
    row = {"task": task_id, "agent": agent.name, "seed": seed,
           "fire_range_m": action["fire_range_m"], "speed_mps": action["speed_mps"],
           "status": "done" if ok else "failed", "decision_ms": round(decision_ms, 3),
           "separation_m": int(sep), "blue_alt_m": int(obs["blue_alt_m"])}
    row.update({k: ("" if v is None else v) for k, v in kpi.items()})
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="tasks.json")
    ap.add_argument("--agents", default="rule,random,scripted")
    ap.add_argument("--episodes", type=int, default=8)
    ap.add_argument("--out", default="results.csv")
    ap.add_argument("--keep", action="store_true", help="keep the scenarios and events under episodes/")
    args = ap.parse_args()

    cfg = json.load(open(os.path.join(ROOT, args.tasks), encoding="utf-8"))
    exe = os.path.join(afsim_root(), "bin", "mission.exe")
    episodes_dir = os.path.join(ROOT, "episodes")
    os.makedirs(episodes_dir, exist_ok=True)

    rows = []
    for task in cfg["tasks"]:
        for name in args.agents.split(","):
            n = 0
            for i in range(args.episodes):
                seed = cfg["seed_base"] + i
                row = run_one(exe, task, make_agent(name, seed), seed,
                              episodes_dir, cfg["end_time_s"])
                rows.append(row)
                n += 1 if row["status"] == "done" else 0
            print("%-8s %-9s %d/%d done" % (task["id"], name, n, args.episodes))

    cols = ["task", "agent", "seed", "status", "outcome", "score", "blue_kill",
            "blue_dead", "shots_blue", "shots_red", "hits_blue", "first_shot_s",
            "end_s", "fire_range_m", "speed_mps", "decision_ms",
            "separation_m", "blue_alt_m"]
    with open(os.path.join(ROOT, args.out), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("wrote", os.path.join(ROOT, args.out), len(rows), "rows")


if __name__ == "__main__":
    main()
