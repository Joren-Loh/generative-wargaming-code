"""The agent interface and three implementations.

One rule for all of them: an agent implements `decide(observation) -> action`.

observation, built by benchmark.py, all SI:
    task_id           str    task family, e.g. "T1_same"
    separation_m      float  initial separation
    blue_alt_m        float  Blue's initial altitude
    red_alt_m         float  Red's initial altitude
    red_speed_mps     float  Red's speed (opponent parameter, public)
    red_fire_range_m  float  Red's fire range (opponent parameter, public)
    max_tof_s         float  the missile's maximum time of flight (a public scenario parameter)
    seed              int    this episode's seed

action, which is written into the scenario and must fall inside the ranges below:
    fire_range_m      10000..28000
    speed_mps         200..350
"""
