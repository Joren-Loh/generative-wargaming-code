"""The scripted agent: one tactical maxim frozen into parameters, standing for experience nobody evaluated.

It picks 26 km because "fire first, break first", a sentence that holds in real air combat
and does not hold in this model: the missile destroys itself before it covers 26 km (see the measurement in the chapter).
It belongs in the benchmark precisely to show that a tactic which sounds right needs data.

This file also stands in for an LLM agent: ask a model for a tactic in conversation and what comes
back is also a fixed set of parameters. The only difference is where the numbers came from.
"""


class ScriptedAgent:
    name = "scripted"

    def decide(self, obs):
        return {"fire_range_m": 26000, "speed_mps": 320}
