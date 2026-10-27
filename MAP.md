# Companion code — English edition

One directory per chapter that has code. Every directory is self-contained: copy it
anywhere, run the entry point named in its `README.md`.

| Directory | Chapter | What it demonstrates | Entry point |
|---|---|---|---|
| `ch01-the-model-chain/` | 1 | What the engine actually models | `scenario.txt, run.bat` |
| `ch02-scenario-anatomy/` | 2 | A scenario you can read line by line | `scenario.txt, run.bat` |
| `ch03-failure-taxonomy/` | 3 | The ten defect classes, reproduced | `scenario_lint.py, broken/, good/` |
| `ch04-retrieval/` | 4 | Guardrail one: retrieval | `extract_knowledge.py, then rag.py` |
| `ch05-schema/` | 5 | Guardrail two: static validation | `schema_check.py` |
| `ch06-repair/` | 6 | Guardrail three: directed repair | `repair.py` |
| `ch07-pipeline/` | 7 | The whole loop, measured | `generate.py, batch_run.py, gates.py` |
| `ch08-layers/` | 8 | Facts versus judgement | `afsim_mcp/tests/test_layers.py` |
| `ch09-mcp-server/` | 9 | A stdio MCP server in one file | `server.py` |
| `ch10-four-tools/` | 10 | Four tools, not forty | `tools/types.py, tools/run.py, tools/analyze.py, tools/launch.py` |
| `ch11-safety/` | 11 | Where the boundary is drawn | `test_rpc.py` |
| `ch12-policy/` | 12 | The policy layer | `agent_demo.py` |
| `ch13-end-to-end/` | 13 | The agent, end to end | `agent_demo.py` |
| `ch14-three-roles/` | 14 | Three roles, one adjudication | `arena.py` |
| `ch15-self-play/` | 15 | One round of self-play | `tournament.py, elo.py` |
| `ch16-skill-library/` | 16 | Skills as data | `skill_library/library.json, skill_library/skill_001/SKILL.md` |
| `ch17-evaluation/` | 17 | Dual-track evaluation | `benchmark.py, report.py` |
| `ch18-ablations/` | 18 | Ablations | `ablation.py` |
| `ch19-dialogue/` | 19 | The conversational wargame | `wargame.py` |
| `ch20-utterance-to-patch/` | 20 | From utterance to patch | `intents.py, patch.py` |
| `ch21-narrative/` | 21 | Narrative bound to events | `narrate.py` |
| `ch23-acceptance/` | 23 | Acceptance | `run.bat, transcript_cmds.txt, _dryrun/dryrun.txt` |

## How this bundle is made

Nothing here is a fork. `make_code_bundle.py` copies the files each chapter quotes out of
the project they were developed in, and writes the table above from the same manifest, so
the bundle and this file cannot disagree. Re-running the script after a fix in the source
refreshes the copy; `python make_code_bundle.py --check` verifies that every directory and
every file it claims is present, and that nothing it does not claim is.

The copy is localised as part of the build. The source project is written in another
language, so every regeneration would otherwise restore its comments and docstrings; the
build replays the line map in `_i18n/code_lines.json`, applies its path and punctuation
rules, and fails rather than ship a file that still contains CJK. Comments, docstrings,
log messages and the recorded transcripts are therefore all English here, and a change to
the source costs a new entry in that map rather than a hand edit in this tree.

Paths inside the files follow the chapter numbering too. A file's header comment names the
upstream directory it was written in, and a recorded run names the scenario it loaded; both
are rewritten on copy to the directory the reader actually has. What is not rewritten is
anything the engine produced from a path it was given at run time.

Three things are deliberately left out: build products (`__pycache__`, `*.pyc`), the binary
replay files an engine run emits (`*.aer`, which also record the absolute path of the
machine that produced them), and the generated episode dumps from the benchmark, which
are large, reproducible, and not quoted anywhere in the book.

## Running anything

- Python 3.10 or newer, standard library only unless the directory's `README.md` says
  otherwise.
- A local AFSIM 2.9 installation for anything that runs the engine. Point at it with the
  `AFSIM_ROOT` environment variable or a `config.json` in the directory; no path is
  hard-coded.
- Commands are given as `python x.py`; on Windows use `py x.py` or the `run.bat` where one
  is shipped.
