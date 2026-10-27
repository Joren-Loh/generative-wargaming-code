# -*- coding: utf-8 -*-
"""
BM25 retriever, standard library only.

Corpus: four kinds of document under knowledge/.
  platform_types.json   one document per platform type (name plus definition site)
  known_includes.json   one document per valid include path
  syntax_snippets.md    split on "## " headings
  error_cases.json      one document per error case

Queries may mix scripts: ASCII runs split on punctuation, CJK runs into unigrams and bigrams.

Usage: python rag.py "air-to-air missile stealth fighter"
"""

import json
import math
import re
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_KNOWLEDGE = _HERE / "knowledge"


def tokenize(text):
    text = text.lower()
    ascii_terms = re.findall(r"[a-z0-9_]+", text)
    cjk = re.findall(r"[\u4e00-\u9fff]+", text)
    cjk_terms = []
    for seg in cjk:
        cjk_terms.extend(seg[i:i + 2] for i in range(len(seg) - 1))
        cjk_terms.extend(seg)
    return ascii_terms + cjk_terms


class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        """docs: [(title, body)]."""
        self.docs = docs
        self.k1, self.b = k1, b
        self.tfs = []
        self.df = {}
        for title, body in docs:
            terms = tokenize(title + " " + title + " " + body)  # title weighted x3
            tf = {}
            for t in terms:
                tf[t] = tf.get(t, 0) + 1
            self.tfs.append(tf)
            for t in tf:
                self.df[t] = self.df.get(t, 0) + 1
        self.avgdl = sum(sum(tf.values()) for tf in self.tfs) / max(len(docs), 1)

    def search(self, query, topk=5):
        q_terms = tokenize(query)
        scores = []
        N = len(self.docs)
        for i, tf in enumerate(self.tfs):
            dl = sum(tf.values())
            s = 0.0
            for t in q_terms:
                if t not in tf:
                    continue
                idf = math.log(1.0 + (N - self.df.get(t, 0) + 0.5) /
                               (self.df.get(t, 0) + 0.5))
                s += idf * tf[t] * (self.k1 + 1.0) / \
                    (tf[t] + self.k1 * (1.0 - self.b + self.b * dl / self.avgdl))
            scores.append((s, i))
        scores.sort(reverse=True)
        return [(s, self.docs[i][0], self.docs[i][1]) for s, i in scores[:topk]
                if s > 0.0]


def load_corpus():
    docs = []
    pt = json.loads((_KNOWLEDGE / "platform_types.json").read_text(encoding="utf-8"))
    for rec in pt.values():
        docs.append(("platform_type " + rec["name"],
                     "platform_type defined in %s" % rec["defined_in"]))
    incs = json.loads((_KNOWLEDGE / "known_includes.json").read_text(encoding="utf-8"))
    for inc in incs:
        docs.append(("include_once " + inc, "a valid include path used by the demos"))
    md = (_KNOWLEDGE / "syntax_snippets.md").read_text(encoding="utf-8")
    for sec in md.split("\n## ")[1:]:
        title, _, body = sec.partition("\n")
        docs.append(("syntax " + title.strip(), body))
    errs = json.loads((_KNOWLEDGE / "error_cases.json").read_text(encoding="utf-8"))
    for e in errs:
        docs.append(("error " + e["error"], e["type"] + " " + e["hint"]))
    return docs


def main():
    import sys
    query = " ".join(sys.argv[1:]) or "stealth fighter air-to-air missile"
    bm25 = BM25(load_corpus())
    print("documents:", len(bm25.docs))
    for s, title, body in bm25.search(query, topk=8):
        print("%8.3f  %s  | %s" % (s, title, body[:60]))


if __name__ == "__main__":
    main()
