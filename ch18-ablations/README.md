# Chapter 18 — Ablations

What each component is worth, one removed at a time: retrieval, schema, repair, self-play. The JSON files are the measurements the chapter reports.

**Entry point:** `ablation.py`

**Run it:**

```
python ablation.py --runs 20
```

**Notes:** Needs a local engine; the shipped JSON lets the tables be checked without one.

**Files in this directory**

- `ablation.py`
- `ablation.json`
- `runs/ablation.json`
