"""The scoring rule agent: it turns "when to shoot" into a formula that reproduces.

Calibration, measured in this chapter: with this model's missile, flight from launch to
detonation takes about 1.7 s/km (27 s for 18 km, 43 s for 26 km).
The maximum time of flight, `max_tof_s`, is 30 s, so the longest reachable range is about
30 / 1.7 = 17.6 km. With a 20% margin the fire range comes out at 14 km.
"""

FLIGHT_S_PER_KM = 1.7     # calibrated from flight_time ≈ 1.7 x range_km
MARGIN = 0.80             # keep 20% of the energy margin


class RuleAgent:
    name = "rule"

    def decide(self, obs):
        reach_km = obs["max_tof_s"] / FLIGHT_S_PER_KM
        fire_km = reach_km * MARGIN
        fire_m = int(max(10000, min(18000, fire_km * 1000)))

        # against a long-range opponent, accelerate to shorten the exposure; otherwise hold an economical speed
        speed = 320 if obs["red_fire_range_m"] > 20000 else 260
        return {"fire_range_m": fire_m, "speed_mps": speed}
