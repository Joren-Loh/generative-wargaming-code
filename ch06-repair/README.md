# Chapter 6 — Guardrail three: directed repair

The error-to-action table: a regex over the engine's verbatim error text, and the deterministic edit it maps to. Repair is a function, not a conversation.

**Entry point:** `repair.py`

**Run it:**

```
python repair.py samples/s01_type_hallucination.txt
```

**Notes:** Needs a local engine for the run-and-parse half.

**Files in this directory**

- `repair.py`
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
