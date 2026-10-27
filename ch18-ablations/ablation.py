# -*- coding: utf-8 -*-
"""
Fixed-plan ablation.

Purpose: to answer "why cannot the learner learn to shoot". With the same evaluation seeds,
run each hand-built fixed plan once and see what the act of shooting is actually worth.

Usage:
    python ablation.py --n 40 --workers 2
Outputs:
    ablation.json  per plan: win rate, launches, mean return
"""

import argparse
import json
import statistics
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from afsim_env import N_PHASES, episode

# in a plan 6=accelerate 7=fire 8=hold
PLANS = {
    "hold all[8,8,8,8]": [8, 8, 8, 8],
    "fire in the back half[8,8,7,7]": [8, 8, 7, 7],
    "fire throughout[7,7,7,7]": [7, 7, 7, 7],
    "accelerate then fire[6,6,7,7]": [6, 6, 7, 7],
}


def _worker(job):
    name, plan, seed = job
    r = episode(seed, plan, shaped=False)
    return dict(name=name, seed=seed, reward=r["reward"], kills=r["kills"],
                fired=r["blue_fired"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--seed-base", type=int, default=100000)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent /
                                         "ablation.json"))
    args = ap.parse_args()

    seeds = list(range(args.seed_base, args.seed_base + args.n))
    jobs = [(name, plan, s) for name, plan in PLANS.items() for s in seeds]
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        rows = list(ex.map(_worker, jobs))

    report = {}
    for name in PLANS:
        sub = [r for r in rows if r["name"] == name]
        n = len(sub)
        win = sum(1 for r in sub if any(k == "red_ftr" for k, _ in r["kills"]))
        loss = sum(1 for r in sub if any(k == "blue_ftr" for k, _ in r["kills"]))
        report[name] = dict(
            n=n,
            win_rate=win / n,
            loss_rate=loss / n,
            mean_reward=sum(r["reward"] for r in sub) / n,
            mean_fired=sum(r["fired"] for r in sub) / n,
        )
        m = report[name]
        print("%-22s win=%.2f  loss=%.2f  mean return=%6.2f  mean launches=%.2f"
              % (name, m["win_rate"], m["loss_rate"], m["mean_reward"], m["mean_fired"]))

    elapsed = time.time() - t0
    Path(args.out).write_text(json.dumps(
        {"elapsed_s": elapsed, "seeds": seeds, "report": report},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print("%d games, %.0f s, results written to %s" % (len(rows), elapsed, args.out))


if __name__ == "__main__":
    main()
