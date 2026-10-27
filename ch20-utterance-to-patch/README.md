# Chapter 20 — From utterance to patch

Nine stages, each with a defined artefact: text, intent, slots, patch, new state. The middle of the chain emits a patch, never a regenerated scenario.

**Entry point:** `intents.py, patch.py`

**Run it:**

```
python -c "import intents; print(intents.parse('set blue 1 altitude to 3000 m'))"
```

**Notes:** Pure standard library.

**Files in this directory**

- `intents.py`
- `patch.py`
- `transcript_cmds.txt`
