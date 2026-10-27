# -*- coding: utf-8 -*-
"""An MCP server on stdio: protocol only, no business logic.

Wire format: one JSON-RPC 2.0 message per line (newline-delimited JSON), UTF-8.
Three methods: initialize / tools/list / tools/call.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from tools import ROUTER, SPECS, ToolError  # noqa: E402
from tools.guard import GuardError  # noqa: E402

PROTOCOL_VERSION = "2024-11-05"


def load_config() -> dict:
    """AFSIM root: the environment variable first, then config.json beside this file."""
    cfg = {}
    path = BASE / "config.json"
    if path.exists():
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            sys.stderr.write(f"config.json failed to parse: {exc}\n")
    root = os.environ.get("AFSIM_ROOT") or cfg.get("afsim_root") or ""
    cfg["afsim_root"] = str(Path(root)) if root else ""
    project = os.environ.get("AFSIM_PROJECT_ROOT") or cfg.get("project_root") or str(BASE)
    cfg["project_root"] = str(Path(project))
    # tools may touch these two directories only: the AFSIM install and this project
    cfg["roots"] = [Path(p) for p in (cfg["afsim_root"], cfg["project_root"]) if p]
    cfg.setdefault("mission_timeout_sec", 120)
    cfg.setdefault("max_output_chars", 20000)
    return cfg


class Server:
    def __init__(self, config: dict):
        self.config = config
        self.tools = ROUTER

    def handle(self, request: dict) -> dict:
        method = request.get("method")
        if method == "initialize":
            return {
                "protocolVersion": PROTOCOL_VERSION,
                "serverInfo": {"name": "afsim-mcp-book", "version": "1.0.0"},
                "capabilities": {"tools": {"listChanged": False}},
            }
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": SPECS}
        if method == "tools/call":
            params = request.get("params") or {}
            name = params.get("name")
            args = params.get("arguments") or {}
            handler = self.tools.get(name)
            if handler is None:
                raise RpcError(-32601, f"Unknown tool: {name}")
            try:
                payload = handler(self.config, args)
            except (ToolError, GuardError) as exc:
                # a business failure travels as isError, not as a JSON-RPC error code
                return wrap({"error": str(exc), "tool": name})
            except Exception as exc:  # a tool may crash, but it must not take the server with it
                return wrap({"error": f"tool raised {exc.__class__.__name__}: {exc}",
                             "tool": name})
            return wrap(payload)
        raise RpcError(-32601, f"Unsupported method: {method}")


class RpcError(Exception):
    def __init__(self, code: int, message: str, data=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


def wrap(payload) -> dict:
    result = {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}]
    }
    if isinstance(payload, dict) and payload.get("error"):
        result["isError"] = True
    return result


def main() -> int:
    for stream in (sys.stdin, sys.stdout):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace", newline="\n")
        except (AttributeError, ValueError):
            pass

    server = Server(load_config())
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except ValueError as exc:
            reply = {"jsonrpc": "2.0", "id": None,
                     "error": {"code": -32700, "message": "Parse error", "data": str(exc)}}
            sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            sys.stdout.flush()
            continue
        is_notification = "id" not in request
        try:
            reply = {"jsonrpc": "2.0", "id": request.get("id"),
                     "result": server.handle(request)}
        except RpcError as exc:
            reply = {"jsonrpc": "2.0", "id": request.get("id"),
                     "error": {"code": exc.code, "message": exc.message}}
        if is_notification:
            continue
        sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
