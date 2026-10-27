# -*- coding: utf-8 -*-
"""Smallest MCP client: translate a plain-language task into a fixed sequence of tool calls.

Not a general agent: the plan is four hard-coded steps. The only thing free to vary is an argument value;
order, failure handling and output size are decided here. That is what a policy layer means.

    python agent_demo.py                        # the default 2v2 scenario
    python agent_demo.py scenarios/broken.txt   # the failure path
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
SCN_DIR = BASE / "scenarios"


class MCPClient:
    def __init__(self):
        self.proc = subprocess.Popen(
            [sys.executable, str(BASE / "server.py")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        self.next_id = 0
        self.trace = []
        self.request("initialize", {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "agent_demo", "version": "1.0"}})
        self.notify("notifications/initialized")

    def _write(self, body: dict) -> None:
        self.proc.stdin.write(json.dumps(body, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def notify(self, method: str) -> None:
        self._write({"jsonrpc": "2.0", "method": method})

    def request(self, method: str, params: dict) -> dict:
        self.next_id += 1
        body = {"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params}
        self._write(body)
        line = self.proc.stdout.readline()
        if not line:
            raise SystemExit("server exited early: " + self.proc.stderr.read()[:500])
        reply = json.loads(line)
        self.trace.append((body, reply))
        print(f"→ {json.dumps(body, ensure_ascii=False)}")
        print(f"← {json.dumps(reply, ensure_ascii=False)[:400]}")
        return reply

    def call(self, name: str, arguments: dict) -> tuple[dict, bool]:
        reply = self.request("tools/call", {"name": name, "arguments": arguments})
        result = reply.get("result", {})
        payload = json.loads(result["content"][0]["text"])
        return payload, bool(result.get("isError"))

    def close(self) -> None:
        self.proc.stdin.close()
        self.proc.wait(timeout=10)


def plan(task: str) -> list[tuple[str, dict]]:
    """The policy layer: task -> four fixed steps, of which only the scenario path comes from the task."""
    scenario = Path(task) if task.endswith(".txt") else SCN_DIR / "duel_2v2.txt"
    if not scenario.is_absolute():
        scenario = (BASE / scenario).resolve()
    return [
        ("afsim_types", {"armed_only": True, "limit": 5}),
        ("run_mission", {"scenario": str(scenario), "timeout_sec": 120}),
        ("analyze_run", {"scenario_dir": str(scenario.parent), "scenario": scenario.stem}),
        ("launch_afsim_tool", {"tool": "warlock", "scenario_file": str(scenario),
                               "dry_run": True}),
    ]


def main() -> int:
    task = sys.argv[1] if len(sys.argv) > 1 else str(SCN_DIR / "duel_2v2.txt")
    print(f"task: run and review {Path(task).name}\n")
    client = MCPClient()
    findings = {}
    failed = False

    for name, arguments in plan(task):
        payload, is_error = client.call(name, arguments)
        findings[name] = payload
        if is_error and not failed:
            failed = True
            print(f"\n[halt] {name} judged a failure: {payload.get('error')}")
            for item in payload.get("errors", []):
                if item.get("file"):
                    print(f"  at: {item['file']}:{item['line']}:{item['column']} "
                          f"{item['severity']} {item['message']}")
            for problem in payload.get("problems", []):
                print(f"  problem: {problem}")
            print("  policy: only a located error goes back to the model to fix; an environment error is not retried.")
            break

    if not failed:
        report = findings["analyze_run"]
        kpi = report["kpi"]
        print("\n===== review =====")
        print(f"platform types available {findings['afsim_types']['total_types']},"
              f"platforms in this run {len(report['platforms'])} (munitions included)")
        print(f"events {sum(report['event_counts'].values())},"
              f"timeline {report['timeline']['first_sec']}-{report['timeline']['last_sec']} s")
        print(f"launched {report['engagements']['fired']} / hits {report['engagements']['hits']} / "
              f"misses {report['engagements']['missed']}")
        print(f"Blue losses {kpi['blue_losses']}, Red losses {kpi['red_losses']},"
              f"time to first shot {kpi['time_to_first_shot_sec']} s")
        print(f"diagnostics: {report['diagnostics'] or 'none (the numbers can be trusted)'}")

    client.close()
    print(f"\n{len(client.trace)} frames exchanged.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
