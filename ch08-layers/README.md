# Chapter 8 — Facts versus judgement

The layer split as code: validation returns facts, policy turns facts into a decision, and a test asserts that nothing in the facts layer imports the policy layer.

**Entry point:** `afsim_mcp/tests/test_layers.py`

**Run it:**

```
python -m pytest afsim_mcp/tests/test_layers.py
```

**Notes:** Quoted from the reference implementation described in this chapter; the test is the argument.

**Files in this directory**

- `afsim_mcp/core/policy.py`
- `afsim_mcp/core/validation.py`
- `afsim_mcp/tests/test_layers.py`
