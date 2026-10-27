---
{
  "id": "skill_001",
  "name": "forward_intercept",
  "description": "A forward intercept during air-defence interception: take the launch position first.",
  "added_iteration": 0
}
---

# forward_intercept

A forward intercept during air-defence interception: take the launch position first.

## Routing

Use this skill when the current self-play generation target matches the name and description above. Load `rules.md` after the skill is selected, and load `examples.jsonl` only when full disclosure or diagnostic expansion is needed.

## Package Files

- `rules.md`: the tactics and the adjudication rule
- `solver_rules.md`: the Blue solving oracle
- `examples.jsonl`: a worked example
- `generator_hints.md`: advice for posing the Red problem
- `validator.py`: `validate_sample(sample)`
- `stats.json`: sampling and curriculum statistics
