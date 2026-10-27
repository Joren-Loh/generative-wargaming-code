# -*- coding: utf-8 -*-
"""tournament.py -- round robin inside one population: N games per pair, sides alternating, win-rate matrix and Elo out.

    python tournament.py                # 6 skills x 4 games per pair = 60 games
    python tournament.py --games 6      # 6 games per pair
    python tournament.py --skills rush_low twin_salvo --games 4
"""

from __future__ import annotations

import argparse
import itertools
import json
import time
from pathlib import Path

import arena
import elo

SHORT = {
    "rush_low": "rush",
    "standoff_high": "stdoff",
    "notch_west": "ntchW",
    "notch_east": "ntchE",
    "twin_salvo": "salvo",
    "dash_low": "dash",
}


def short(name: str) -> str:
    return SHORT.get(name, name[:6])


def run(skill_ids: list[str], games_per_pair: int, seed0: int) -> list[dict]:
    skills = arena.load_skills()
    results = []
    total = 0
    started = time.perf_counter()
    for a, b in itertools.combinations(skill_ids, 2):
        for i in range(games_per_pair):
            seed = seed0 + i
            # sides alternate: A plays Blue on even games, B on odd, which cancels the side bias
            if i % 2 == 0:
                record = arena.play(skills[a], skills[b], seed, tag=f"{a}_vs_{b}")
            else:
                record = arena.play(skills[b], skills[a], seed, tag=f"{b}_vs_{a}")
            arena.archive(record)
            results.append(record)
            total += 1
            flag = "-" if record["error"] else f"{record['winner']}/{record['reason']}"
            print(f"[{total:02d}] {a:14s} vs {b:14s} seed={seed} "
                  f"{record['elapsed_ms']:4d} ms  {flag}")
    print(f"\n{total} games, wall clock {time.perf_counter() - started:.1f} s")
    return results


def report(results: list[dict], skill_ids: list[str]) -> None:
    table = elo.ratings_from_games(results)
    matrix = elo.win_matrix(results, skill_ids)

    width = max(len(short(s)) for s in skill_ids) + 2
    header = "".ljust(width) + "".join(short(s).rjust(8) for s in skill_ids)
    print("\nWin-rate matrix (row against column; 1.00 = wins everything)")
    print(header)
    for a in skill_ids:
        cells = []
        for b in skill_ids:
            value = matrix.get((a, b))
            cells.append("     —" if value != value else f"{value:8.2f}")
        print(short(a).ljust(width) + "".join(cells))

    print("\nElo ranking (K=24, starting at 1500)")
    print("rank  skill            Elo     games  W   D   L   win rate")
    for i, (name, rating, n, w, d, l) in enumerate(elo.ranking(table), 1):
        rate = w / n if n else 0.0
        print(f"{i:>3}   {name:<15s} {rating:7.1f} {n:5d} {w:3d} {d:3d} {l:3d}  {rate:5.2f}")

    errors = [r for r in results if r["error"]]
    draws = [r for r in results if r["winner"] == "draw"]
    print(f"\ninvalid games {len(errors)}, draws {len(draws)},"
          f"mean per game {sum(r['elapsed_ms'] for r in results) / max(len(results), 1):.0f} ms")
    out = Path(__file__).resolve().parent / "runs" / "tournament.json"
    out.write_text(json.dumps(
        {"games": results, "ratings": table,
         "matrix": {f"{a}|{b}": v for (a, b), v in matrix.items() if v == v}},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"details written to {out}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=4, help="games per pair of skills")
    parser.add_argument("--seed", type=int, default=2000)
    parser.add_argument("--skills", nargs="*", default=None)
    args = parser.parse_args()

    skill_ids = args.skills or sorted(arena.load_skills())
    results = run(skill_ids, args.games, args.seed)
    report(results, skill_ids)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
