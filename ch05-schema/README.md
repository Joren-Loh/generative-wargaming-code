# Chapter 5 — Guardrail two: static validation

Fifteen rules that reject a scenario without running it, and the ten broken samples they are tested against. Milliseconds, no engine, no token cost.

**Entry point:** `schema_check.py`

**Run it:**

```
python schema_check.py samples/s01_type_hallucination.txt
```

**Notes:** Pure standard library.

**Files in this directory**

- `schema_check.py`
- `samples/README.md`
- `samples/s01_type_hallucination.txt`
- `samples/s02_bad_include.txt`
- `samples/s03_unclosed_block.txt`
- `samples/s04_coord_swapped.txt`
- `samples/s05_bad_unit.txt`
- `samples/s06_undeclared_var.txt`
- `samples/s07_evt_no_enable.txt`
- `samples/s08_semantic_altitude.txt`
- `samples/s09_coincident_wp.txt`
- `samples/s10_position_with_speed.txt`
- `knowledge/platform_types.json`
