# Chapter 2 — A scenario you can read line by line

The 2v2 engagement used throughout Part I, together with the four artefacts a run produces: console output, .evt event file, mission.log and stats.json.

**Entry point:** `scenario.txt, run.bat`

**Run it:**

```
mission.exe scenario.txt, then compare with expected/stats.json
```

**Notes:** Runs on a local AFSIM 2.9 installation. `output/` holds the recorded run: the console text, the .evt event file and the log. The .aer replay file is not shipped — run.bat regenerates it in a few seconds, and it is binary.

**Files in this directory**

- `README.md`
- `console.txt`
- `expected/scenario.evt.excerpt.txt`
- `expected/stats.json`
- `mission.log`
- `output/scenario.evt`
- `output/scenario.log`
- `run.bat`
- `run.txt`
- `scenario.txt`
- `stages/console1.txt`
- `stages/console2.txt`
- `stages/console3.txt`
- `stages/mission.log`
- `stages/stage1.txt`
- `stages/stage2.txt`
- `stages/stage3.txt`
- `stages/output/stage1.evt`
- `stages/output/stage1.log`
- `stages/output/stage2.evt`
- `stages/output/stage2.log`
- `stages/output/stage3.evt`
- `stages/output/stage3.log`
- `timing.txt`
