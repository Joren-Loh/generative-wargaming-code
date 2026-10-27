# -*- coding: utf-8 -*-
"""Turn the .evt event stream into sentences a person can read.

Iron rule: every sentence must point back to one event, one field. Nothing here is a
reasonable guess: what is not known is not said. Better one sentence short than one invented.
"""

import re

REC = re.compile(r"^\s*(\d+\.\d+)\s+([A-Z_]+)\s*(.*)$")


def cn_name(pid):
    """blue_1 -> Blue 1; blue_1_aam_2 -> Blue 1's 2nd missile"""
    m = re.match(r"^(blue|red)_(\d+)(?:_aam_(\d+))?$", pid)
    if not m:
        return pid
    side = "Blue" if m.group(1) == "blue" else "Red"
    if m.group(3):
        return "%s %s's %s missile" % (side, m.group(2), {1: "1st", 2: "2nd", 3: "3rd"}.get(int(m.group(3)), "%sth" % m.group(3)))
    return "%s %s" % (side, m.group(2))


def parse_evt(path):
    """Split the multi-line continuation records of a .evt into [{time, type, args, raw}]"""
    events, cur = [], None
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = REC.match(line.rstrip("\n"))
            if m:
                if cur:
                    events.append(cur)
                cur = {"time": float(m.group(1)), "type": m.group(2),
                       "args": m.group(3).split(), "raw": line.rstrip("\n")}
            elif cur is not None:
                cur["raw"] += " " + line.strip()
    if cur:
        events.append(cur)
    return events


def _num(evt, key, default=None):
    m = re.search(r"%s:\s*(-?[\d.]+)" % re.escape(key), evt["raw"])
    return float(m.group(1)) if m else default


def _word(evt, key, default=""):
    m = re.search(r"%s:\s*(\S+)" % re.escape(key), evt["raw"])
    return m.group(1) if m else default


# event -> sentence template. A placeholder may reference only a field the event really has.
TEMPLATES = {
    "SENSOR_TRACK_INITIATED":
        "at {t:.0f} s {origin}'s radar detects {target} at {rng:.1f} km",
    "WEAPON_FIRED":
        "at {t:.0f} s {origin} launches 1 missile at {target} ({weapon})",
    "WEAPON_HIT":
        "at {t:.1f} s {weapon} hits, Pk={pk:.2f}, engine adjudicates {result}",
    "WEAPON_MISSED":
        "at {t:.1f} s {weapon} misses",
    "PLATFORM_BROKEN":
        "at {t:.1f} s {origin} is shot down",
    "PLATFORM_ADDED":
        "at {t:.0f} s {origin} ({type}) enters the battle",
}

NARRATE_ORDER = ("PLATFORM_ADDED", "SENSOR_TRACK_INITIATED", "WEAPON_FIRED",
                 "WEAPON_HIT", "WEAPON_MISSED", "PLATFORM_BROKEN")


def sentences(events, keep=None, limit=40):
    """Generate the sentences in time order. keep is the set of event types worth keeping; by default a missile destroying itself is noise and is dropped."""
    keep = keep or set(NARRATE_ORDER)
    out = []
    for e in events:
        if e["type"] not in keep or e["type"] not in TEMPLATES:
            continue
        a = e["args"]
        if e["type"] == "PLATFORM_BROKEN" and (len(a) < 3 or a[2] != "FIGHTER"):
            continue                     # a self-destroyed missile stays out, or three noise lines bury one result
        if e["type"] == "PLATFORM_ADDED" and (len(a) < 3 or a[2] != "FIGHTER"):
            continue
        tpl = TEMPLATES[e["type"]]
        out.append(tpl.format(
            t=e["time"],
            origin=cn_name(a[0]) if a else "?",
            target=cn_name(a[1]) if len(a) > 1 else "?",
            weapon=cn_name(a[2]) if len(a) > 2 else "?",
            rng=(_num(e, "Truth: Range") or _num(e, "Range") or 0) / 1000.0,
            pk=_num(e, "Pk", 0.0) or 0.0,
            result=_word(e, "Result", "NONE"),
            type=(a[2] if e["type"] == "PLATFORM_ADDED" and len(a) > 2 else ""),
        ))
        if len(out) >= limit:
            out.append("... (the remaining events are in output/scenario.evt)")
            break
    return out


def summary(events):
    """Count only what can be counted: launches, hits, platforms destroyed."""
    s = {"fired": {"blue": 0, "red": 0}, "hits": {"blue": 0, "red": 0},
         "killed": [], "first_shot": None, "first_kill": None, "duration": 0.0}
    for e in events:
        a = e["args"]
        if e["type"] == "WEAPON_FIRED":
            s["fired"]["blue" if a[0].startswith("blue") else "red"] += 1
            s["first_shot"] = s["first_shot"] or e["time"]
        elif e["type"] == "WEAPON_HIT":
            s["hits"]["blue" if a[0].startswith("blue") else "red"] += 1
        elif e["type"] == "PLATFORM_BROKEN" and len(a) > 2 and a[2] == "FIGHTER":
            s["killed"].append({"time": e["time"], "name": a[0],
                                "side": "blue" if a[0].startswith("blue") else "red"})
            s["first_kill"] = s["first_kill"] or e["time"]
        elif e["type"] == "PLATFORM_DELETED":
            s["duration"] = max(s["duration"], e["time"])
    return s


def report(events, end_time=0.0):
    s = summary(events)
    lines = ["Blue fired %d, hit %d; Red fired %d, hit %d."
             % (s["fired"]["blue"], s["hits"]["blue"],
                s["fired"]["red"], s["hits"]["red"])]
    if s["killed"]:
        lines.append("Shot down: " + ", ".join(
            "%s (%g s)" % (cn_name(k["name"]), k["time"]) for k in s["killed"]) + ".")
    else:
        lines.append("No platform was adjudicated destroyed.")
    if s["first_shot"] is not None:
        lines.append("First shot at %g s." % s["first_shot"])
    lines.append("Run length %g s." % (end_time or s["duration"]))
    return "\n".join(lines)


def answer(question, events):
    """Pick the shape of the answer from the question's keywords; every number still comes from the event stream."""
    s = summary(events)
    if re.search(r"missile|fired|launch|how many", question):
        return "Blue fired %d and hit %d; Red fired %d and hit %d." % (
            s["fired"]["blue"], s["hits"]["blue"], s["fired"]["red"], s["hits"]["red"])
    if re.search(r"who|loss|shot down|alive|left", question):
        if not s["killed"]:
            return "The event stream holds no PLATFORM_BROKEN (FIGHTER) record, so neither side lost an aircraft."
        return "Shot down: " + ", ".join(
            "%s (%.1f s)" % (cn_name(k["name"]), k["time"]) for k in s["killed"]) + \
            ", %d in total." % len(s["killed"])
    if re.search(r"how long|duration|time", question):
        return "Run length %.1f s, first launch at %.0f s." % (s["duration"], s["first_shot"] or 0)
    return report(events)
