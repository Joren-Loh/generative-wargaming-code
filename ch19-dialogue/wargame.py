# -*- coding: utf-8 -*-
"""Conversational wargaming: utterance -> intent -> patch -> scenario -> engine -> narration.

Usage:
    python wargame.py                        # interactive
    python wargame.py --batch transcript_cmds.txt   # replay a script, writing an archivable record

Three separations: language stops at the patch, adjudication belongs to mission.exe, and narration only transcribes the event stream.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import intents
import narrate
import patch

ROOT = Path(__file__).resolve().parent
BASE_TEXT = (ROOT / "scenario_base.txt").read_text(encoding="utf-8")
HISTORY = ROOT / "output" / "patches.jsonl"

PHASES = ("IDLE", "BUILDING", "RUNNING", "REVIEW")
LEGAL = {
    "IDLE":     {"BUILD", "ADD", "SET_TIME", "QUERY"},
    "BUILDING": {"ADD", "MOVE", "SET_TIME", "RUN", "UNDO", "BUILD", "QUERY"},
    "RUNNING":  {"ABORT"},
    "REVIEW":   {"QUERY", "REPLAY", "EXPORT", "MOVE", "ADD", "SET_TIME", "RUN", "BUILD", "UNDO"},
}

DEFAULT = {"type": "FIGHTER", "alt": 8000.0, "speed": 250.0}


def find_engine():
    for c in [os.environ.get("AFSIM_ROOT"),
              json.loads((ROOT / "config.json").read_text())["afsim_root"]
              if (ROOT / "config.json").exists() else None,
              str(ROOT.parents[2] / "afsim-2.9.0")]:
        if c and (Path(c) / "bin" / "mission.exe").exists():
            return Path(c) / "bin" / "mission.exe"
    raise SystemExit("mission.exe not found: set AFSIM_ROOT, or write config.json here")


class Session(object):
    def __init__(self, quiet=False):
        self.phase = "IDLE"
        self.pending = None
        self.state = {"end_time": 300.0, "platforms": {}}
        self.events = []
        self.last_wall = 0.0
        self.quiet = quiet
        HISTORY.parent.mkdir(exist_ok=True)

    # ---------------------------------------------------------------- helpers
    def _log(self, op, path, value, note):
        patch.append_history(HISTORY, {"ts": time.strftime("%H:%M:%S"), "op": op,
                                       "path": path, "value": value, "note": note})

    def _commit(self, p, note):
        """Apply a patch; on failure return the error and write nothing, to disk or to history."""
        try:
            self.state = patch.apply(self.state, p)
        except patch.PatchError as e:
            return "patch refused: %s" % e
        self._log(p["op"], p["path"], p.get("value"), note)
        return None

    # ---------------------------------------------------------------- dispatch
    def handle(self, text):
        it = intents.parse(text)
        if self.pending is not None and not it.matched:
            it = intents.parse(text, self.pending)   # not understood this turn: treat it as the answer to the last question
        self.pending = None
        if it.name not in LEGAL[self.phase]:
            return ["Current state %s does not accept \"%s\". What you can do: %s."
                    % (self.phase, intents.SPEC[it.name][0],
                       ", ".join(intents.SPEC[x][0] for x in sorted(LEGAL[self.phase])))]
        if it.missing:
            self.pending = it
            return ["One thing is missing: " + intents.FOLLOW_UP[it.missing[0]]]
        return getattr(self, "do_" + it.name.lower())(it)

    def do_build(self, it):
        self.state = {"end_time": 300.0, "platforms": {}}
        self.phase = "BUILDING"
        # the reset marker: undo replays from here, or it would replay the previous turn's patches too
        self._log("reset", "", None, "new scenario")
        return ["Cleared. You can deploy forces now, e.g. \"two Blue F-16s enter from the east, altitude 8000 m\"."]

    def do_add(self, it):
        if "unsupported" in it.slots:
            return ["The base scenario defines one platform type, FIGHTER, so %s is not supported."
                    "To add a type, edit scenario_base.txt and put it in patch.TYPES." % it.slots["unsupported"]]
        side, n = it.slots["side"], int(it.slots.get("count", 1))
        heading = it.slots.get("heading") or ("east" if side == "blue" else "west")
        alt = it.slots.get("alt", DEFAULT["alt"])
        speed = it.slots.get("speed", DEFAULT["speed"])
        base_lon = 122.00 if side == "blue" else 122.45
        replies = []
        for i in range(1, n + 1):
            name = "%s_%d" % (side, len([k for k in self.state["platforms"]
                                        if k.startswith(side)]) + 1)
            v = {"type": it.slots.get("type", DEFAULT["type"]), "side": side,
                 "lat": round(30.0 + 0.15 * (i - 1), 3), "lon": base_lon,
                 "alt": alt, "speed": speed, "heading": heading}
            err = self._commit(patch.make("add_platform", "/platforms/" + name, v),
                               "%s: add platform" % it.text.strip())
            replies.append("Refused: " + err if err else "Added %s (%s, altitude %g m, heading %s)."
                           % (narrate.cn_name(name), v["type"], alt,
                              {"east": "east", "west": "west", "north": "north",
                               "south": "south"}[heading]))
        self.phase = "BUILDING"
        added = [k for k in sorted(self.state["platforms"]) if k.startswith(side)]
        return ["Added %d platforms: %s." % (n, ", ".join(narrate.cn_name(k) for k in added))]

    def do_move(self, it):
        name = it.slots["name"]
        if name not in self.state["platforms"]:
            return ["No platform called %s. Currently: %s." %
                    (narrate.cn_name(name),
                     ", ".join(narrate.cn_name(k) for k in sorted(self.state["platforms"])))]
        if "bad_heading" in it.slots:
            return ["Heading accepts only east, south, west and north; %s would need a two-leg route, which is not supported."
                    % it.slots["bad_heading"]]
        unit = {"alt": ("altitude", " m"), "speed": ("speed", " m/s"),
                "heading": ("heading", "")}
        done = []
        for f in ("alt", "speed", "heading"):
            if f not in it.slots:
                continue
            err = self._commit(patch.make("set", "/platforms/%s/%s" % (name, f), it.slots[f]),
                               "%s (change %s)" % (it.text.strip(), f))
            if err:
                return ["Refused: " + err]
            v = it.slots[f]
            done.append("%s %s%s" % (unit[f][0], "%g" % v if isinstance(v, float) else v,
                                     unit[f][1]))
        if not done:
            return ["Change what on %s? Say \"altitude 9000 m\", \"speed 300 m/s\" or \"to the north\"." %
                    narrate.cn_name(name)]
        return ["Changed %s: %s. Run again for it to take effect." % (narrate.cn_name(name), ", ".join(done))]

    def do_set_time(self, it):
        sec = float(it.slots["seconds"])
        err = self._commit(patch.make("set", "/end_time", sec), "%s: set duration" % it.text.strip())
        return ["Refused: " + err] if err else ["Run length set to %g s." % sec]

    def do_run(self, it):
        problems = patch.runnable(self.state)
        if problems:
            return ["Cannot run yet: " + "; ".join(problems) + "."]
        self.phase = "RUNNING"
        pre = self._dry_run()
        if pre:
            self.phase = "REVIEW" if self.events else "BUILDING"
            return ["The scenario did not compile, so nothing ran: " + pre]
        rc, out, wall = self._run_engine(self.state)
        if rc != 0:
            self.phase = "BUILDING"
            return ["Engine exit code %d, the run did not finish. First error: %s" % (rc, self._first_error(out))]
        self.events = narrate.parse_evt(ROOT / "output" / "scenario.evt")
        self.phase = "REVIEW"
        keep = {"WEAPON_HIT", "WEAPON_MISSED", "PLATFORM_BROKEN"}
        lines = narrate.sentences(self.events, keep=keep, limit=10)
        return ["Run complete (return code 0, wall clock %.2f s, %d events)." % (wall, len(self.events))] + \
               lines + [narrate.report(self.events, self.state["end_time"])]

    def do_query(self, it):
        if not self.events:
            return ["No run to report yet. Say \"run simulation\" first."]
        return [narrate.answer(it.text, self.events)]

    def do_replay(self, it):
        if not self.events:
            return ["No event stream to replay."]
        return narrate.sentences(self.events, limit=40)

    def do_export(self, it):
        if not self.events:
            return ["Nothing to export yet."]
        out = ROOT / "output" / "report.md"
        body = ["# Simulation report", "", "## Scenario", "",
                "```text", patch.render(self.state, BASE_TEXT), "```", "",
                "## Event narrative", ""] + ["- " + s for s in narrate.sentences(self.events)] + \
               ["", "## Statistics", "", narrate.report(self.events, self.state["end_time"])]
        out.write_text("\n".join(body), encoding="utf-8")
        return ["Wrote %s (%d bytes)." % (out.relative_to(ROOT).as_posix(), out.stat().st_size)]

    def do_undo(self, it):
        rows = patch.load_history(HISTORY)
        ops = ("add_platform", "remove_platform", "set")
        start = max([i for i, r in enumerate(rows) if r["op"] == "reset"], default=-1) + 1
        seg = [r for r in rows[start:] if r["op"] in ops]
        if not seg:
            return ["No patch to undo."]
        # replay this turn's patches except the last, to get the previous state
        state = {"end_time": 300.0, "platforms": {}}
        for r in seg[:-1]:
            state = patch.apply(state, {"op": r["op"], "path": r["path"], "value": r["value"]})
        last = seg[-1]
        self.state = state
        patch.append_history(HISTORY, {"ts": time.strftime("%H:%M:%S"), "op": "undo",
                                       "path": last["path"], "value": None,
                                       "note": "undo: " + last["note"]})
        return ["Undone: \"%s\" (%s %s)." % (last["note"], last["op"], last["path"])]

    def do_abort(self, it):
        self.phase = "IDLE"
        return ["Aborted, back to idle. The scenario file stays in scenario.txt."]

    # ---------------------------------------------------------------- engine
    def _first_error(self, out):
        for line in out.splitlines():
            if "ERROR" in line or "FATAL" in line:
                return line.strip()[:160]
        return "(the engine wrote no ERROR line)"

    def _run_engine(self, state):
        (ROOT / "scenario.txt").write_text(patch.render(state, BASE_TEXT), encoding="utf-8")
        (ROOT / "output").mkdir(exist_ok=True)
        t0 = time.time()
        r = subprocess.run([str(find_engine()), "scenario.txt"], cwd=str(ROOT),
                           capture_output=True, text=True, errors="ignore", timeout=600)
        wall = time.time() - t0
        self.last_wall = wall
        return r.returncode, (r.stdout or "") + (r.stderr or ""), wall

    def _dry_run(self):
        """Run once with end_time squeezed to 1 s, only to find out whether the edit still compiles."""
        d = ROOT / "_dryrun"
        (d / "output").mkdir(parents=True, exist_ok=True)
        trial = dict(self.state, end_time=1.0)
        (d / "dryrun.txt").write_text(patch.render(trial, BASE_TEXT), encoding="utf-8")
        r = subprocess.run([str(find_engine()), "dryrun.txt"], cwd=str(d),
                           capture_output=True, text=True, errors="ignore", timeout=120)
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode != 0 or "Simulation complete" not in out:
            return self._first_error(out)
        return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", default=None, help="read user input from a file, one line per turn")
    ap.add_argument("--out", default=None, help="write the dialogue record to a file")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    s = Session()
    lines = []

    def say(who, text):
        for ln in text.splitlines():
            lines.append("%s %s" % (who, ln) if ln else "")
        print("\n".join([(("%s %s" % (who, ln)) if ln else "") for ln in text.splitlines()]))

    say("System", "Conversational wargame ready (AFSIM 2.9.0). Say \"new scenario\" first, or deploy forces directly.")

    if args.batch:
        cmds = [l.strip() for l in Path(args.batch).read_text(encoding="utf-8").splitlines()
                if l.strip() and not l.startswith("#")]
        for c in cmds:
            say("Director", c)
            say("System", "\n".join(s.handle(c)))
    else:
        while True:
            try:
                c = input("\nDirector > ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if c in ("exit", "quit", "bye"):
                break
            if c:
                say("Director", c)
                say("System", "\n".join(s.handle(c)))

    if args.out:
        Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
