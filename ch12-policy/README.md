# Chapter 12 — The policy layer

What happens after a tool returns an error: a fixed four-step plan, at most three rounds, and the difference between a located error and an unlocated one.

**Entry point:** `agent_demo.py`

**Run it:**

```
python agent_demo.py --scenario scenarios/broken.txt
```

**Notes:** Runs against the server above; needs a local engine. The policy module itself is in ch08-layers/afsim_mcp/core/policy.py.

**Files in this directory**

- `agent_demo.py`
