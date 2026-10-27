# Generative Wargaming — companion code

Code for *Generative Wargaming: Building LLM Agents for Combat Simulation*, select edition.
One directory per chapter that has code: twenty-two directories, Chapters 1 to 21 and 23
(Chapter 22 is an argument, not a program). Every directory is self-contained: copy it
anywhere, run the entry point named in its `README.md`, and it works — no path is hard-coded.

`MAP.md` is the index: which directory belongs to which chapter, what it demonstrates, and
where to start reading. It is generated from the same manifest as the directories, so the two
cannot disagree.

## Running anything

- Python 3.10 or newer, standard library only unless the chapter's `README.md` says otherwise.
- A local AFSIM 2.9 installation for anything that runs the engine. Point at it with the
  `AFSIM_ROOT` environment variable or a `config.json` in the directory.
- Commands are written `python x.py`; on Windows use `py x.py`, or the `run.bat` where one is
  shipped.

## What is not here

Binary artefacts a run produces (`*.aer`) are not committed: they are large, they record the
absolute path of the machine that produced them, and `run.bat` regenerates them in seconds.
Benchmark episode dumps are likewise reproducible from the scripts beside them.

## Licence

The code is provided for study and research use. The text of the book is not part of this
repository and remains copyright of the author. Corrections to the code are welcome as issues
here; errata for the text go through the book's listing page.
