"""The random agent: uniform sampling over the action space, as a lower bound.

Its job is not to win but to be the baseline for not thinking at all. Any agent
that cannot beat random has learned less than guessing.
"""

import random


class RandomAgent:
    name = "random"

    def __init__(self, seed=0):
        self._rng = random.Random(seed)

    def decide(self, obs):
        return {
            "fire_range_m": self._rng.randrange(10000, 28001, 500),
            "speed_mps": self._rng.randrange(200, 351, 10),
        }
