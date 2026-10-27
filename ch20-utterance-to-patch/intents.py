# -*- coding: utf-8 -*-
"""Rule-based intent parsing: regexes plus keywords.

Why not a model on the first hop: the intent set is closed at ten and the slots are finite at seven,
so at this scale a regex is more accurate than a general model, and every parse can be replayed line by line.
Attaching a model replaces parse() and nothing else.
"""

import re

CN = {"zero": 0, "one": 1, "two": 2, "a couple": 2, "three": 3, "four": 4,
      "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}

SIDE_WORDS = {"blue": "blue", "red": "red", "blu": "blue", "reed": "red"}
DIR_WORDS = {"east": "east", "west": "west", "south": "south", "north": "north"}
TYPE_WORDS = ("F-16", "F16", "f-16", "J-10", "J10", "fighter", "fighters")

# name -> (description, required slots)
SPEC = {
    "BUILD":   ("new scenario", []),
    "ADD":     ("add platform", ["side"]),
    "MOVE":    ("change platform", ["name"]),
    "SET_TIME": ("set duration", ["seconds"]),
    "RUN":     ("run simulation", []),
    "QUERY":   ("query results", []),
    "REPLAY":  ("replay events", []),
    "EXPORT":  ("export results", []),
    "UNDO":    ("undo the last step", []),
    "ABORT":   ("abort the run", []),
}

FOLLOW_UP = {
    "side": "Which side does this flight belong to? Blue or Red?",
    "name": "Which platform? Just the number, e.g. \"Blue 1\".",
    "seconds": "How long should the run be? E.g. \"10 minutes\" or \"600 seconds\".",
}


class Intent(object):
    def __init__(self, name, slots=None, text="", matched=True):
        self.name = name
        self.slots = slots or {}
        self.text = text
        self.matched = matched      # False = no rule matched, so the fallback answered
        self.missing = [s for s in SPEC[name][1] if s not in self.slots]

    def __repr__(self):
        return "Intent(%s, %s)" % (self.name, self.slots)


def _num(s):
    """'two' / '12' / 'ten' -> int"""
    if s is None:
        return None
    if s.isdigit():
        return int(s)
    if s == "ten":
        return 10
    if s.startswith("ten"):
        return 10 + CN.get(s[1:], 0)
    if s.endswith("ten"):
        return CN.get(s[0], 0) * 10
    return CN.get(s)


def _side(text):
    m = re.search(r"\b(blue|red)\b", text, re.I)
    return SIDE_WORDS.get(m.group(1).lower()) if m else None


def extract_slots(text):
    s = {}
    side = _side(text)
    if side:
        s["side"] = side
    m = re.search(r"(?:^\s*|\b(?:add|deploy|put|place|bring)\s+)(\d+|one|two|three|four|five|six|seven|eight|nine|ten|a couple)\b", text, re.I)
    if m:
        s["count"] = _num(m.group(1))
    if any(w in text for w in TYPE_WORDS):
        s["type"] = "FIGHTER"
    m = re.search(r"altitude\D{0,8}?(\d+(?:\.\d+)?)\s*(km|m)\b", text, re.I)
    if m:
        v = float(m.group(1))
        s["alt"] = v * 1000 if m.group(2).lower() == "km" else v
    m = re.search(r"speed\D{0,10}?(\d+(?:\.\d+)?)\s*(m/s|m/sec)", text, re.I)
    if m:
        s["speed"] = float(m.group(1))
    two = re.search(r"\b(north-?east|north-?west|south-?east|south-?west)\b", text, re.I)
    if two:
        s["bad_heading"] = two.group(1)      # four headings only, so a diagonal must be refused outright
    else:
        m = re.search(r"\b(east|west|south|north)\b", text, re.I)
        if m:
            s["heading"] = DIR_WORDS[m.group(1)]
    m = re.search(r"\b(aew|awacs|bomber|transport|tanker|drone|helicopter)\b", text, re.I)
    if m:
        s["unsupported"] = m.group(1)
    m = re.search(r"\b(?:blue|red)\s*(\d+)\b", text, re.I)
    if m:
        s["name"] = "%s_%s" % (side, m.group(1)) if side else None
        if not s["name"]:
            del s["name"]
    m = re.search(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:minutes?|min)\b", text, re.I)
    if m:
        s["seconds"] = _num(m.group(1)) * 60
    else:
        m = re.search(r"\b(\d+)\s*(?:seconds?|secs?)\b", text, re.I)
        if m:
            s["seconds"] = int(m.group(1))
    return s


# keyword -> intent, highest priority first: the more final an action, the earlier it sits
RULES = [
    ("ABORT",  r"(?i)\b(abort|stop|cancel|break it off|call it off|pack it in)\b"),
    ("UNDO",   r"(?i)\b(undo|revert|withdraw|roll back|rollback)\b"),
    ("EXPORT", r"(?i)\b(export|generate report|archive|save a copy)\b"),
    ("REPLAY", r"(?i)\b(replay|rerun|review|rewind)\b"),
    ("QUERY",  r"(?i)\b(results?|outcome|who was|who got|losses|how many|statistics|report|killed|shot down)\b"),
    ("RUN",    r"(?i)\b(run simulation|run the simulation|start|execute)\b"),
    ("MOVE",   r"(?i)\b(set|change|adjust|move|switch|raise|lower|speed up|slow down|accelerate)\b"),
    ("ADD",    r"(?i)(\b(aircraft|fighters?|enter|entering|add|deploy|put|place|bring)\b|\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(blue|red)\b)"),
    ("BUILD",  r"(?i)\b(new|clear|reset|from scratch|start over)\b"),
    ("SET_TIME", r"(?i)(\d+\s*(?:minutes?|seconds?|min|s)\b|\bduration\b)"),
]


def parse(text, pending=None):
    """Return an Intent. pending is last turn's incomplete intent, whose missing slot this turn answers first."""
    slots = extract_slots(text)
    if pending is not None:
        merged = dict(pending.slots)
        merged.update({k: v for k, v in slots.items() if v})
        return Intent(pending.name, merged, text)
    for name, pattern in RULES:
        if re.search(pattern, text):
            return Intent(name, slots, text)
    return Intent("QUERY", slots, text, matched=False)   # fallback: treat it as a question, never as an order
