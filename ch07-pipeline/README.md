# Chapter 7 — The whole loop, measured

One requirement in, a verified scenario out: retrieval, generation, post-processing, schema check, engine run, repair. Includes the parameter table and the batch runner behind the numbers in this chapter.

**Entry point:** `generate.py, batch_run.py, gates.py`

**Run it:**

```
python generate.py --requirement "2v2, blue wins", or run.bat for the batch
```

**Notes:** Runs end to end with the offline surrogate; set OLLAMA_HOST for a real model.

**Files in this directory**

- `README.md`
- `batch_run.py`
- `gates.py`
- `generate.py`
- `generated/index.csv`
- `generated/run_001/manifest.json`
- `generated/run_001/mission.log`
- `generated/run_001/scenario.txt`
- `generated/run_001/output/_seed_0.txt`
- `generated/run_001/output/_seed_1.txt`
- `generated/run_001/output/_seed_2.txt`
- `generated/run_001/output/_seed_3.txt`
- `generated/run_001/output/scenario.evt`
- `generated/run_001/output/scenario.log`
- `generated/run_002/manifest.json`
- `generated/run_002/mission.log`
- `generated/run_002/scenario.txt`
- `generated/run_002/output/_seed_0.txt`
- `generated/run_002/output/_seed_1.txt`
- `generated/run_002/output/_seed_2.txt`
- `generated/run_002/output/_seed_3.txt`
- `generated/run_002/output/scenario.evt`
- `generated/run_002/output/scenario.log`
- `generated/run_003/manifest.json`
- `generated/run_003/mission.log`
- `generated/run_003/scenario.txt`
- `generated/run_003/output/_seed_0.txt`
- `generated/run_003/output/_seed_1.txt`
- `generated/run_003/output/_seed_2.txt`
- `generated/run_003/output/_seed_3.txt`
- `generated/run_003/output/scenario.evt`
- `generated/run_003/output/scenario.log`
- `generated/run_004/manifest.json`
- `generated/run_004/mission.log`
- `generated/run_004/scenario.txt`
- `generated/run_004/output/_seed_0.txt`
- `generated/run_004/output/_seed_1.txt`
- `generated/run_004/output/_seed_2.txt`
- `generated/run_004/output/_seed_3.txt`
- `generated/run_004/output/scenario.evt`
- `generated/run_004/output/scenario.log`
- `generated/run_005/manifest.json`
- `generated/run_005/mission.log`
- `generated/run_005/scenario.txt`
- `generated/run_005/output/_seed_0.txt`
- `generated/run_005/output/_seed_1.txt`
- `generated/run_005/output/_seed_2.txt`
- `generated/run_005/output/_seed_3.txt`
- `generated/run_005/output/scenario.evt`
- `generated/run_005/output/scenario.log`
- `generated/run_006/manifest.json`
- `generated/run_006/mission.log`
- `generated/run_006/scenario.txt`
- `generated/run_006/output/_seed_0.txt`
- `generated/run_006/output/_seed_1.txt`
- `generated/run_006/output/_seed_2.txt`
- `generated/run_006/output/_seed_3.txt`
- `generated/run_006/output/scenario.evt`
- `generated/run_006/output/scenario.log`
- `library/base/aircraft_base.txt`
- `library/base/fighter_base.txt`
- `library/processors/shooter.txt`
- `library/sensors/geo_radar.txt`
- `library/theater/blue_fighter.txt`
- `library/weapons/aam_implicit.txt`
- `params.csv`
- `reports/baseline.json`
- `reports/batch_results.csv`
- `reports/batch_summary.json`
- `reports/gates_report.txt`
- `run.bat`
- `samples/bad_block.txt`
- `samples/bad_position.txt`
- `samples/dead_scenario.txt`
- `samples/mission.log`
- `samples/output/dead.log`
- `samples/output/scenario.evt`
- `templates/scenario.tmpl`
