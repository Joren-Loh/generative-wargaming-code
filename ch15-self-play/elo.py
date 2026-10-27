# -*- coding: utf-8 -*-
"""elo.py -- Elo updates and a win-rate matrix over a batch of games.

Elo answers "who is stronger relative to whom", never "how strong in absolute terms": it depends
on the opponent pool, and swapping the pool reorders the table. That is why the chapter wants two tracks.
"""

from __future__ import annotations

DEFAULT_RATING = 1500.0
DEFAULT_K = 24.0


def expected(ra: float, rb: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))


def update(ra: float, rb: float, score_a: float, k: float = DEFAULT_K) -> tuple[float, float]:
    """score_a: 1 for a win, 0.5 for a draw, 0 for a loss. Both sides share K, so the system is zero-sum."""
    delta = k * (score_a - expected(ra, rb))
    return ra + delta, rb - delta


def ratings_from_games(games: list[dict], k: float = DEFAULT_K) -> dict[str, dict]:
    """Feed games in chronological order; return each skill's Elo, game count and win/draw/loss."""
    table: dict[str, dict] = {}

    def slot(skill):
        return table.setdefault(skill, {"elo": DEFAULT_RATING, "games": 0, "w": 0, "d": 0, "l": 0})

    for game in games:
        if game["winner"] not in ("blue", "red", "draw"):
            continue  # an invalid game never enters the rating
        blue, red = game["blue"], game["red"]
        score_blue = {"blue": 1.0, "red": 0.0, "draw": 0.5}[game["winner"]]
        a, b = slot(blue), slot(red)
        a["elo"], b["elo"] = update(a["elo"], b["elo"], score_blue, k)
        for item, score in ((a, score_blue), (b, 1.0 - score_blue)):
            item["games"] += 1
            item["w" if score == 1.0 else "d" if score == 0.5 else "l"] += 1
    return table


def ranking(table: dict[str, dict]) -> list[tuple[str, float, int, int, int, int]]:
    rows = [(name, round(v["elo"], 1), v["games"], v["w"], v["d"], v["l"])
            for name, v in table.items()]
    return sorted(rows, key=lambda row: -row[1])


def win_matrix(games: list[dict], skills: list[str]) -> dict[tuple[str, str], float]:
    """(A, B) -> A's score rate against B. Mirrored games are normalised per skill, so the side played does not matter."""
    buckets: dict[tuple[str, str], list[float]] = {}
    for game in games:
        if game["winner"] not in ("blue", "red", "draw"):
            continue
        blue, red = game["blue"], game["red"]
        score_blue = {"blue": 1.0, "red": 0.0, "draw": 0.5}[game["winner"]]
        buckets.setdefault((blue, red), []).append(score_blue)
        buckets.setdefault((red, blue), []).append(1.0 - score_blue)
    matrix = {}
    for (a, b), scores in buckets.items():
        matrix[(a, b)] = sum(scores) / len(scores)
    for name in skills:
        matrix[(name, name)] = float("nan")
    return matrix
