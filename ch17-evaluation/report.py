"""Collapse results.csv into a table worth quoting: proportions get an interval, means get an n.

    python report.py
    python report.py --csv results.csv --md summary.md

Wilson intervals rather than the normal approximation: at n=8 the normal approximation puts
the lower bound below zero, while Wilson stays bounded at 0/8 and 8/8, which is how this chapter dares print 0%.
"""

import argparse
import csv
import math
from collections import defaultdict

BLOCKS = " .:-=+*#%@"


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def fisher_greater(a, b, c, d):
    """One-sided Fisher exact test: is group 1's success rate higher than group 2's?"""
    n = a + b + c + d
    row1, col1 = a + b, a + c
    def pmf(x):
        return math.comb(col1, x) * math.comb(n - col1, row1 - x) / math.comb(n, row1)
    obs = pmf(a)
    return sum(pmf(x) for x in range(a, min(row1, col1) + 1) if pmf(x) <= obs + 1e-12)


def pct(k, n):
    lo, hi = wilson(k, n)
    return "%.0f%% [%.0f, %.0f]" % (100 * k / n if n else 0, 100 * lo, 100 * hi)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="results.csv")
    ap.add_argument("--md", default="summary.md")
    args = ap.parse_args()

    rows = [r for r in csv.DictReader(open(args.csv, encoding="utf-8"))
            if r["status"] == "done"]
    if not rows:
        raise SystemExit("no successful games")

    cells = defaultdict(list)
    for r in rows:
        cells[(r["task"], r["agent"])].append(r)

    agents = sorted({r["agent"] for r in rows})
    tasks = sorted({r["task"] for r in rows})
    out = []
    out.append("## Main table (each cell, n = %d)\n" % len(cells[(tasks[0], agents[0])]))
    out.append("| Task | Agent | Kill rate | Survival | W/D/L | First shot (s) | Hits/launches | Decide (ms) |")
    out.append("|---|---|---|---|---|---|---|---|")
    for t in tasks:
        for a in agents:
            v = cells[(t, a)]
            n = len(v)
            kill = sum(int(r["blue_kill"]) for r in v)
            surv = sum(1 - int(r["blue_dead"]) for r in v)
            w = sum(1 for r in v if r["outcome"] == "blue")
            l = sum(1 for r in v if r["outcome"] == "red")
            fs = [float(r["first_shot_s"]) for r in v if r["first_shot_s"]]
            hits = sum(int(r["hits_blue"]) for r in v)
            shots = sum(int(r["shots_blue"]) for r in v)
            dm = sum(float(r["decision_ms"]) for r in v) / n
            out.append("| %s | %s | %s | %s | %d/%d/%d | %.1f | %d/%d | %.2f |"
                       % (t, a, pct(kill, n), pct(surv, n), w, n - w - l, l,
                          sum(fs) / len(fs) if fs else 0.0, hits, shots, dm))

    out.append("\n## By agent (both tasks merged)\n")
    out.append("| Agent | n | Kill rate | Survival | Mean first shot (s) |")
    out.append("|---|---|---|---|---|")
    merged = {}
    for a in agents:
        v = [r for t in tasks for r in cells[(t, a)]]
        n = len(v)
        kill = sum(int(r["blue_kill"]) for r in v)
        surv = sum(1 - int(r["blue_dead"]) for r in v)
        fs = [float(r["first_shot_s"]) for r in v if r["first_shot_s"]]
        merged[a] = (kill, surv, n)
        out.append("| %s | %d | %s | %s | %.1f |"
                   % (a, n, pct(kill, n), pct(surv, n), sum(fs) / len(fs) if fs else 0.0))

    out.append("\n## Kill-rate matrix (one character per cell, @ = 100%)\n")
    out.append("| Agent \\ Task | " + " | ".join(tasks) + " |")
    out.append("|---|" + "---|" * len(tasks))
    for a in agents:
        line = ["**%s**" % a]
        for t in tasks:
            v = cells[(t, a)]
            k = sum(int(r["blue_kill"]) for r in v)
            rate = k / len(v)
            bar = BLOCKS[min(9, int(rate * 9 + 0.5))] * 5
            line.append("%s %d/%d" % (bar, k, len(v)))
        out.append("| " + " | ".join(line) + " |")

    out.append("\n## Significance (one-sided Fisher, kill counts)\n")
    out.append("| Comparison | Kills | p | Verdict |")
    out.append("|---|---|---|---|")
    for t in tasks:
        for i in range(len(agents)):
            for j in range(i + 1, len(agents)):
                a, b = agents[i], agents[j]
                ka, kb = merged[a][0], merged[b][0]
                na, nb = merged[a][2], merged[b][2]
                # a one-sided test has to point at the higher group; computed alphabetically it returns the reverse p, near 1.
                if ka >= kb:
                    p = fisher_greater(ka, na - ka, kb, nb - kb)
                    pair, hit = "%s > %s" % (a, b), "%d/%d vs %d/%d" % (ka, na, kb, nb)
                else:
                    p = fisher_greater(kb, nb - kb, ka, na - ka)
                    pair, hit = "%s > %s" % (b, a), "%d/%d vs %d/%d" % (kb, nb, ka, na)
                verdict = "significant (p<0.05)" if p < 0.05 else "not significant"
                out.append("| %s | %s | %.3f | %s |" % (pair, hit, p, verdict))
        break      # the pooled sample is used once

    text = "\n".join(out)
    print(text)
    with open(args.md, "w", encoding="utf-8") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()
