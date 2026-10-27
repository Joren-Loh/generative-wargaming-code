# -*- coding: utf-8 -*-
"""A scenario patch: an op / path / value triple, checkable and reversible.

state is a plain data dictionary, shaped like this:

    {"end_time": 300,
     "platforms": {"blue_1": {"type": "FIGHTER", "side": "blue",
                              "lat": 30.0, "lon": 122.0, "alt": 8000.0,
                              "speed": 250.0, "heading": "east"}}}

A patch says where to change and what to change it to, and never regenerates the whole scenario.
"""

import copy
import json

SIDES = ("blue", "red")
TYPES = ("FIGHTER",)          # the only type the base scenario defines, deliberately narrow
HEADINGS = ("east", "west", "north", "south")
LIMITS = {"alt": (100.0, 15000.0), "speed": (100.0, 600.0),
          "lat": (-85.0, 85.0), "lon": (-180.0, 180.0),
          "end_time": (10.0, 3600.0)}
PATH_LEN_DEG = 0.5            # offset of the route's second point, about 48 km


class PatchError(Exception):
    pass


def make(op, path, value=None):
    return {"op": op, "path": path, "value": value}


# --------------------------------------------------------------------- path
def _split(path):
    """'/platforms/blue_1/alt' -> ['platforms', 'blue_1', 'alt']"""
    if not path.startswith("/"):
        raise PatchError("a path must start with /: %s" % path)
    return [p for p in path.split("/")[1:] if p]


def get(state, path):
    cur = state
    for k in _split(path):
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            raise PatchError("no such path: %s" % path)
    return cur


# --------------------------------------------------------------------- apply
def apply(state, patch):
    """Return a new state with the patch applied; the original is untouched. A failure raises PatchError."""
    new = copy.deepcopy(state)
    op, path, value = patch["op"], patch["path"], patch.get("value")
    keys = _split(path)

    if op == "add_platform":
        if len(keys) != 2 or keys[0] != "platforms":
            raise PatchError("add_platform needs a path of the form /platforms/<name>")
        name = keys[1]
        if name in new["platforms"]:
            raise PatchError("platform %s already exists; it cannot be added twice" % name)
        new["platforms"][name] = copy.deepcopy(value)
    elif op == "remove_platform":
        if len(keys) != 2 or keys[0] != "platforms":
            raise PatchError("remove_platform needs a path of the form /platforms/<name>")
        if keys[1] not in new["platforms"]:
            raise PatchError("no platform %s" % keys[1])
        del new["platforms"][keys[1]]
    elif op == "set":
        cur = new
        for k in keys[:-1]:
            if k not in cur:
                raise PatchError("no such path: %s" % path)
            cur = cur[k]
        if keys[-1] not in cur:
            raise PatchError("no such field: %s" % path)
        cur[keys[-1]] = value
    else:
        raise PatchError("unknown operation: %s" % op)

    problems = validate(new)
    if problems:
        raise PatchError("; ".join(problems))
    return new


# --------------------------------------------------------------------- checks
def validate(state):
    """Return a list of problems; an empty list means it can be rendered. Every rule comes from a hard engine constraint."""
    out = []
    lo, hi = LIMITS["end_time"]
    if not lo <= state.get("end_time", 0) <= hi:
        out.append("end_time must be between %g and %g seconds" % (lo, hi))
    for name, p in state.get("platforms", {}).items():
        if p.get("type") not in TYPES:
            out.append("%s has type %s, which is undefined (only %s exists)" % (name, p.get("type"), "/".join(TYPES)))
        if p.get("side") not in SIDES:
            out.append("%s has side %s, which is illegal (blue or red only)" % (name, p.get("side")))
        if p.get("heading") not in HEADINGS:
            out.append("%s has heading %s, which is illegal" % (name, p.get("heading")))
        for f in ("lat", "lon", "alt", "speed"):
            lo, hi = LIMITS[f]
            v = p.get(f)
            if not isinstance(v, (int, float)) or not lo <= v <= hi:
                out.append("%s has %s=%s, outside %g to %g" % (name, f, v, lo, hi))
        if p.get("heading") in ("east", "west") and abs(p.get("lon", 0) + PATH_LEN_DEG) > 179.0:
            out.append("%s sits too close to 180E; its route would double back" % name)
    return out


def runnable(state):
    """Whole-scenario checks, run before a simulation: one patch need not satisfy them, the finished scenario must."""
    out = []
    if not state.get("platforms"):
        out.append("a scenario needs at least one platform before it can be simulated")
    sides = {p["side"] for p in state.get("platforms", {}).values() if "side" in p}
    if len(sides) < 2:
        out.append("at least one Blue and one Red are needed, or nothing will engage")
    return out


# --------------------------------------------------------------------- render
def _dms(deg, pos, neg):
    """Decimal degrees -> deg:min:sec. The carry matters: 30.15 written as 30:08:60.0 is illegal to the engine."""
    hemi = pos if deg >= 0 else neg
    total = round(abs(deg) * 3600.0, 1)
    d, rest = divmod(total, 3600.0)
    m, s = divmod(rest, 60.0)
    return "%02d:%02d:%04.1f%s" % (int(d), int(m), s, hemi)


def _route_points(p):
    lat, lon, h = p["lat"], p["lon"], p["heading"]
    if h == "east":
        p2 = (lat, lon + PATH_LEN_DEG)
    elif h == "west":
        p2 = (lat, lon - PATH_LEN_DEG)
    elif h == "north":
        p2 = (lat + PATH_LEN_DEG, lon)
    else:
        p2 = (lat - PATH_LEN_DEG, lon)
    return (lat, lon), p2


def render(state, base_text):
    """Fill state into the base scenario and return the complete scenario text."""
    blocks = []
    for name in sorted(state["platforms"]):
        p = state["platforms"][name]
        (lat1, lon1), (lat2, lon2) = _route_points(p)
        blocks.append(
            "platform %s %s\n"
            "   side %s\n"
            "   route\n"
            "      position %s %s altitude %g m msl speed %g m/sec\n"
            "      position %s %s altitude %g m msl speed %g m/sec\n"
            "   end_route\n"
            "end_platform\n"
            % (name, p["type"], p["side"],
               _dms(lat1, "n", "s"), _dms(lon1, "e", "w"), p["alt"], p["speed"],
               _dms(lat2, "n", "s"), _dms(lon2, "e", "w"), p["alt"], p["speed"])
        )
    return (base_text
            .replace("@@PLATFORMS@@", "\n".join(blocks).rstrip(), 1)
            .replace("@@END_TIME@@", "%g" % state["end_time"], 1))


# --------------------------------------------------------------------- history
def load_history(path):
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def append_history(path, entry):
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
