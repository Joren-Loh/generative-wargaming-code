# Chapter 23 — Acceptance

The dry run that decides whether the whole project is finished: a fixed script of utterances, a fixed expected report, and a diff that either matches or does not.

**Entry point:** `run.bat, transcript_cmds.txt, _dryrun/dryrun.txt`

**Run it:**

```
run.bat, then diff _dryrun/dryrun.txt against transcript.txt
```

**Notes:** Needs a local engine; this is the run the book's last chapter reports.

**Files in this directory**

- `run.bat`
- `transcript.txt`
- `transcript_cmds.txt`
- `scenario_base.txt`
- `_dryrun/dryrun.txt`
- `_dryrun/mission.log`
- `_dryrun/output/scenario.evt`
- `_dryrun/output/scenario.log`
- `output/report.md`
