# Chapter 16 — Skills as data

A skill is a JSON record with a schema, a validator and a version - not a prompt. The library and one worked skill show what a stored skill has to contain.

**Entry point:** `skill_library/library.json, skill_library/skill_001/SKILL.md`

**Run it:**

```
python skill_library/skill_001/validator.py
```

**Notes:** Pure standard library.

**Files in this directory**

- `skill_library/library.json`
- `skill_library/skill_001/SKILL.md`
- `skill_library/skill_001/examples.jsonl`
- `skill_library/skill_001/generator_hints.md`
- `skill_library/skill_001/rules.md`
- `skill_library/skill_001/solver_rules.md`
- `skill_library/skill_001/stats.json`
- `skill_library/skill_001/validator.py`
