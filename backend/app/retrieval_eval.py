"""Retrieval evaluation: BM25 alone, embeddings alone and the hybrid the tutor uses (no tutor calls).

    BB_MOCK_LLM=0 python -m app.retrieval_eval --course-id 1

Runs the labelled questions in eval_data/retrieval_1805.json through the course's public index (`Index.retrieve`,
as in a tutor turn) and reports, per method and question style, how often the top 6 contains a relevant chunk
(hit@6), where the first one sits (MRR), and how many of the 6 are relevant (precision@6). Chunks missing an
embedding are filled in first (about a cent for 18.05, once); each run then embeds the 47 questions (well under a
cent). Labels are by material: a chunk is relevant if its document title starts with one of the question's prefixes.
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

from . import config, embeddings, knowledge, llm
from .db import init_db

QUESTIONS = Path(__file__).parent / "eval_data" / "retrieval_1805.json"
STYLES = ["all", "keyword", "paraphrase", "notation"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compare BM25, embedding and hybrid retrieval on labelled questions.")
    ap.add_argument("--course-id", type=int, default=1)
    ap.add_argument("--json", help="also write per-question results to this file")
    args = ap.parse_args(argv)
    if config.MOCK_LLM or not config.OPENROUTER_API_KEY:
        print("Needs the real embedding model: set OPENROUTER_API_KEY and BB_MOCK_LLM=0.", file=sys.stderr)
        return 1
    init_db()
    filled = embeddings.backfill(args.course_id)
    kb = knowledge.cache.get(args.course_id)
    index, k = kb.index, config.TOP_K
    qs = json.loads(QUESTIONS.read_text())["questions"]
    qv = [embeddings.unit(v) for v in llm.embed("eval", [q["q"] for q in qs])]

    methods = {
        "bm25 (before)": lambda q, v: index.retrieve(q, None, k),
        "embeddings": lambda q, v: [c for _, c in index.dense_search(v, k)],
        "hybrid (app)": lambda q, v: index.retrieve(q, v, k),
    }
    rows, agg = [], defaultdict(lambda: defaultdict(list))
    for q, v in zip(qs, qv):
        row = {"q": q["q"], "style": q["style"]}
        for name, fn in methods.items():
            got = fn(q["q"], v)
            rel = [any(c.title.startswith(p) for p in q["relevant"]) for c in got]
            first = next((r + 1 for r, ok in enumerate(rel) if ok), None)
            m = {"hit": float(any(rel)), "mrr": 1 / first if first else 0.0, "p": sum(rel) / k}
            for style in (q["style"], "all"):
                for key, val in m.items():
                    agg[name, style][key].append(val)
            row[name] = {**m, "top": [f"{c.title} p.{c.page}" for c in got]}
        rows.append(row)

    counts = {s: sum(1 for q in qs if s == "all" or q["style"] == s) for s in STYLES}
    print(f"\n{len(qs)} questions, {index.n} public chunks ({int(index.has_vec.sum())} embedded, {filled} just now), "
          f"top {k}, {config.EMBED_MODEL}, similarity floor {config.EMBED_MIN_SIMILARITY}\n")
    for metric, label in (("hit", "hit@6"), ("mrr", "MRR"), ("p", "precision@6")):
        print(f"{label:<16}" + "".join(f"{s} ({counts[s]})".rjust(18) for s in STYLES))
        for name in methods:
            print(f"  {name:<14}" + "".join(f"{np.mean(agg[name, s][metric]):18.2f}" for s in STYLES))
        print()
    print("Misses (no relevant chunk in the top 6):")
    for name in methods:
        missed = [r["q"] for r in rows if not r[name]["hit"]]
        print(f"  {name}: {len(missed)}")
        for m in missed:
            print(f"    - {m}")
    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
