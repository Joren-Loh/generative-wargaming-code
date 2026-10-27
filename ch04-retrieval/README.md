# Chapter 4 — Guardrail one: retrieval

The knowledge base extracted from a local installation - 428 platform types, 952 includes - and the BM25 retriever that puts the three most relevant syntax snippets in front of the model.

**Entry point:** `extract_knowledge.py, then rag.py`

**Run it:**

```
python extract_knowledge.py --root %AFSIM_ROOT%   (once)
```

**Notes:** The corpus is built from whatever AFSIM installation you point it at; the counts in the book come from a 2.9 install.

**Files in this directory**

- `rag.py`
- `extract_knowledge.py`
- `knowledge/error_cases.json`
- `knowledge/knowledge.json`
- `knowledge/known_includes.json`
- `knowledge/platform_types.json`
- `knowledge/syntax_snippets.md`
- `run.bat`
