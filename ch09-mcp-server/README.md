# Chapter 9 — A stdio MCP server in one file

JSON-RPC over stdin/stdout, four tools, no third-party packages. The transport is the part most examples get wrong, so it is here in full.

**Entry point:** `server.py`

**Run it:**

```
python server.py   (then send JSON-RPC on stdin)
```

**Notes:** Pure standard library; no pip install of the MCP SDK is needed.

**Files in this directory**

- `server.py`
- `config.json`
- `tools/__init__.py`
- `tools/analyze.py`
- `tools/guard.py`
- `tools/launch.py`
- `tools/run.py`
- `tools/types.py`
- `run.bat`
