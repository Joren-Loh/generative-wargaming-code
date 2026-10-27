# -*- coding: utf-8 -*-
"""Hand-built JSON-RPC requests, checked frame by frame against the MCP server.

No MCP SDK: write the request as one JSON line into the child's stdin, read one reply line,
print the raw frame, then assert on the key fields. Every protocol detail stays visible that way.

    python test_rpc.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
PY = sys.executable
SCN = BASE / "scenarios"


def frame(req_id, method, params=None):
    body = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        body["params"] = params
    return json.dumps(body, ensure_ascii=False)


class Client:
    """Smallest stdio client: one frame per line, UTF-8."""

    def __init__(self):
        self.proc = subprocess.Popen(
            [PY, str(BASE / "server.py")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )

    def send(self, line: str) -> dict:
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()
        reply = self.proc.stdout.readline()
        if not reply:
            raise RuntimeError("server did not reply: " + self.proc.stderr.read()[:400])
        return json.loads(reply)

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=10)


def payload(reply: dict) -> dict:
    return json.loads(reply["result"]["content"][0]["text"])


def show(title: str, obj: dict) -> None:
    print(f"\n----- {title} -----")
    print(json.dumps(obj, ensure_ascii=False)[:900])


def main() -> int:
    client = Client()
    failures = []

    def expect(cond: bool, label: str) -> None:
        print(f"[{'PASS' if cond else 'FAIL'}] {label}")
        if not cond:
            failures.append(label)

    # 1. initialize
    reply = client.send(frame(1, "initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {}, "clientInfo": {"name": "test_rpc", "version": "1.0"}}))
    show("initialize", reply)
    expect(reply["result"]["protocolVersion"] == "2024-11-05", "initialize returns the protocol version")
    expect(reply["result"]["capabilities"]["tools"]["listChanged"] is False,
           "initialize declares the tools capability")

    # 2. a notification deserves no reply: send tools/list right after it, and the next frame read must be the list
    client.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
    client.proc.stdin.flush()
    reply = client.send(frame(2, "tools/list"))
    tools = reply["result"]["tools"]
    show("tools/list", {"count": len(tools), "names": [t["name"] for t in tools]})
    expect(len(tools) == 4, "tools/list returns four tools")
    expect(reply["id"] == 2, "the notification produced no reply frame (ids stay aligned)")

    # 3. afsim_types: the default listing
    reply = client.send(frame(3, "tools/call", {
        "name": "afsim_types", "arguments": {"keyword": "FIGHTER", "limit": 5}}))
    types = payload(reply)
    show("afsim_types(keyword=FIGHTER)", types)
    expect(types.get("total_types", 0) > 100, "the type catalogue holds more than 100")

    # 4. run_mission: a healthy scenario
    reply = client.send(frame(4, "tools/call", {
        "name": "run_mission",
        "arguments": {"scenario": str(SCN / "duel_2v2.txt")}}))
    run = payload(reply)
    show("run_mission(duel_2v2)", run)
    expect(run.get("ok") is True, "the 2v2 scenario is judged a success")
    expect(run["outputs"]["evt_events"] > 10, "the .evt holds more than ten events")

    # 5. analyze_run: the report for the same directory
    reply = client.send(frame(5, "tools/call", {
        "name": "analyze_run", "arguments": {"scenario_dir": str(SCN)}}))
    report = payload(reply)
    show("analyze_run", report)
    expect(report.get("evt_bytes", 0) > 0, "the report read a non-empty .evt")

    # 6. launch_afsim_tool: dry_run only locates the executable
    reply = client.send(frame(6, "tools/call", {
        "name": "launch_afsim_tool", "arguments": {"tool": "wizard", "dry_run": True}}))
    launch = payload(reply)
    show("launch_afsim_tool(wizard)", launch)

    # 7. a failing call: an undefined platform_type, expecting isError=true
    reply = client.send(frame(7, "tools/call", {
        "name": "run_mission", "arguments": {"scenario": str(SCN / "broken.txt")}}))
    broken = payload(reply)
    show("run_mission(broken), the failure case", broken)
    expect(reply.get("result", {}).get("isError") is True, "a failing call carries isError=true")
    expect(any(e.get("file") for e in broken.get("errors", [])), "the errors carry a file location")

    # 8. a failing call: an inert run (exit code alone would call it a success)
    reply = client.send(frame(8, "tools/call", {
        "name": "run_mission", "arguments": {"scenario": str(SCN / "inert.txt")}}))
    inert = payload(reply)
    show("run_mission(inert)", inert)
    expect(inert.get("returncode") == 0, "the inert run exits with code 0")
    expect(inert.get("ok") is False, "the inert run is still judged a failure")

    # 9. an unknown method
    reply = client.send(frame(9, "tools/unknown"))
    show("unknown method", reply)
    expect(reply.get("error", {}).get("code") == -32601, "an unknown method returns -32601")

    client.close()
    print("\nfailures:", failures or "none")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
