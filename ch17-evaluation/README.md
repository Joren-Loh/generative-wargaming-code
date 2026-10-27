# Chapter 17 — Dual-track evaluation

Same seeds, same opponent, same KPIs, three agents on one table: a rule agent, a trained policy and the language-model stack. 'Which is stronger' becomes a number that can be recomputed.

**Entry point:** `benchmark.py, report.py`

**Run it:**

```
python benchmark.py --seeds 2000-2003, then python report.py
```

**Notes:** Needs a local engine and several minutes per agent.

**Files in this directory**

- `benchmark.py`
- `report.py`
- `agents/base.py`
- `agents/random_agent.py`
- `agents/rule_agent.py`
- `agents/scripted_agent.py`
- `config.json`
- `scenario_template.txt`
