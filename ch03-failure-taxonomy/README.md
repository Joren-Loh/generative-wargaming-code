# Chapter 3 — The ten defect classes, reproduced

Ten broken scenarios and eight correct ones, plus the static checker that names each defect. Every error string in the book was produced by running these files.

**Entry point:** `scenario_lint.py, broken/, good/`

**Run it:**

```
python scenario_lint.py broken/s01_type_hallucination.txt
```

**Notes:** Runs on Python 3.10+ and a local engine.

**Files in this directory**

- `README.md`
- `bad/README.md`
- `bad/bad01-unknown-platform-type.txt`
- `bad/bad02-latlon-reversed.txt`
- `bad/bad03-position-with-speed.txt`
- `bad/bad04-coincident-waypoints.txt`
- `bad/bad05-event-output-no-enable.txt`
- `bad/bad06-missing-side.txt`
- `bad/bad07-cout-in-script.txt`
- `bad/bad08-nested-script-in-on-init.txt`
- `bad/bad09-pulse-width-unit.txt`
- `bad/bad10-mover-unsupported-param.txt`
- `bad/mission.log`
- `bad/output/scenario.evt`
- `good/good01-minimal-platform/mission.log`
- `good/good01-minimal-platform/scenario.txt`
- `good/good01-minimal-platform/output/scenario.evt`
- `good/good02-route-navigation/mission.log`
- `good/good02-route-navigation/scenario.txt`
- `good/good02-route-navigation/output/scenario.evt`
- `good/good03-named-route/mission.log`
- `good/good03-named-route/scenario.txt`
- `good/good03-named-route/output/scenario.evt`
- `good/good04-global-script-variables/mission.log`
- `good/good04-global-script-variables/scenario.txt`
- `good/good04-global-script-variables/output/scenario.evt`
- `good/good05-type-inheritance/mission.log`
- `good/good05-type-inheritance/scenario.txt`
- `good/good05-type-inheritance/output/scenario.evt`
- `good/good06-execute-scheduling/mission.log`
- `good/good06-execute-scheduling/scenario.txt`
- `good/good06-execute-scheduling/output/scenario.evt`
- `good/good07-dms-coords/mission.log`
- `good/good07-dms-coords/scenario.txt`
- `good/good07-dms-coords/output/scenario.evt`
- `good/good08-include-chain/mission.log`
- `good/good08-include-chain/scenario.txt`
- `good/good08-include-chain/output/scenario.evt`
- `good/good08-include-chain/platforms/fighter_types.txt`
- `scenario_lint.py`
