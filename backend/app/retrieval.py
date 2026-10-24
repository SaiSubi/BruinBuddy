"""Hybrid retrieval over one course's public chunks, plus the one helper that touches tutor-only solutions.

`Index.retrieve` fuses two rankings by reciprocal rank: BM25 (exact course terms, "Problem 3", names) and cosine
similarity of chunk embeddings (paraphrases, notation; see embeddings.py). Without a query vector or chunk vectors
it is BM25 alone. An `Index` only ever holds chunks students may see (knowledge.py decides which). Protected
solution chunks are reachable only through `solution_chunks_for`, which feeds the checker and is never shown to the
tutor.
"""
import math
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass

import numpy as np

from . import config, llm
from .db import db

STOP = set("""a an and are as at be but by can do does for from how i if in is it its me my of on or so than that
the their then there these this to us was we what when where which who why will with you your about into just
not no yes please tell explain give show help need want""".split())

_tok = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text).lower()
    out = []
    for t in _tok.findall(text):
        if t in STOP:
            continue
        if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(t)
    return out


@dataclass
class Chunk:
    id: int
    doc_id: str
    title: str
    kind: str
    page: int
    text: str


class Index:
    k1, b = 1.5, 0.75

    def __init__(self, chunks: list[Chunk], vectors: list[np.ndarray | None] | None = None) -> None:
        self.chunks = chunks
        self.by_id = {c.id: c for c in chunks}
        self.pos = {c.id: i for i, c in enumerate(chunks)}
        self.tok = [tokens((c.title + " ") * 3 + c.text) for c in chunks]
        self.dl = [len(t) for t in self.tok]
        self.avgdl = (sum(self.dl) / len(self.dl)) if self.dl else 1.0
        self.post: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for i, t in enumerate(self.tok):
            for term, tf in Counter(t).items():
                self.post[term].append((i, tf))
        self.n = len(chunks)
        self.tokset = [set(t) for t in self.tok]
        # unit vectors, one row per chunk; a chunk without one (or of another size) gets a zero row and never ranks
        dims = Counter(len(v) for v in vectors or [] if v is not None)
        self.dim = dims.most_common(1)[0][0] if dims else 0
        self.vecs = np.zeros((self.n, self.dim), dtype=np.float32)
        self.has_vec = np.zeros(self.n, dtype=bool)
        for i, v in enumerate(vectors or []):
            if v is not None and len(v) == self.dim:
                self.vecs[i], self.has_vec[i] = v, True

    @property
    def dense(self) -> bool:
        return bool(self.has_vec.any())

    def _bm25(self, query: str) -> dict[int, float]:
        scores: dict[int, float] = defaultdict(float)
        for term in set(tokens(query)):
            plist = self.post.get(term)
            if not plist:
                continue
            idf = math.log(1 + (self.n - len(plist) + 0.5) / (len(plist) + 0.5))
            for i, tf in plist:
                norm = tf + self.k1 * (1 - self.b + self.b * self.dl[i] / self.avgdl)
                scores[i] += idf * tf * (self.k1 + 1) / norm
        return scores

    def search(self, query: str, k: int = 6, *, exclude_docs: set[str] | frozenset = frozenset(),
               only_docs: set[str] | None = None) -> list[tuple[float, Chunk]]:
        out = []
        for i, s in sorted(self._bm25(query).items(), key=lambda kv: -kv[1]):
            c = self.chunks[i]
            if c.doc_id in exclude_docs or (only_docs is not None and c.doc_id not in only_docs):
                continue
            out.append((s, c))
            if len(out) >= k:
                break
        return out

    def _allowed(self, c: Chunk, exclude_docs, only_docs) -> bool:
        return c.doc_id not in exclude_docs and (only_docs is None or c.doc_id in only_docs)

    def dense_search(self, qvec: np.ndarray, k: int = 6, *, exclude_docs: set[str] | frozenset = frozenset(),
                     only_docs: set[str] | None = None) -> list[tuple[float, Chunk]]:
        if not self.dense or len(qvec) != self.dim:
            return []
        floor = llm.embed_floor()
        sims = np.where(self.has_vec, self.vecs @ qvec, -np.inf)
        out = []
        for i in np.argsort(-sims):
            if sims[i] < floor:
                break  # weaker matches (and chunks without a vector) are left to BM25
            c = self.chunks[i]
            if self._allowed(c, exclude_docs, only_docs):
                out.append((float(sims[i]), c))
                if len(out) >= k:
                    break
        return out

    def retrieve(self, query: str, qvec: np.ndarray | None, k: int = 6, *,
                 exclude_docs: set[str] | frozenset = frozenset(), only_docs: set[str] | None = None) -> list[Chunk]:
        """The top k chunks for a query: BM25 hits above the floor, fused with embedding hits by reciprocal rank."""
        pool = max(k, config.HYBRID_POOL)
        lexical = [c for s, c in self.search(query, pool, exclude_docs=exclude_docs, only_docs=only_docs)
                   if s >= config.MIN_RETRIEVAL_SCORE]
        semantic = ([c for _, c in self.dense_search(qvec, pool, exclude_docs=exclude_docs, only_docs=only_docs)]
                    if qvec is not None else [])
        if not semantic:
            return lexical[:k]
        score: dict[int, float] = defaultdict(float)
        by_id: dict[int, Chunk] = {}
        for ranking in (lexical, semantic):
            for rank, c in enumerate(ranking):
                score[c.id] += 1 / (config.RRF_K + rank + 1)
                by_id[c.id] = c
        return [by_id[i] for i in sorted(score, key=lambda i: -score[i])[:k]]

    def explain(self, query: str, qvec: np.ndarray | None, chunks: list[Chunk]) -> list[dict]:
        """How each returned chunk scored, for tracing: BM25 and cosine similarity, and its rank in each list
        (1 = best, over the whole course; None = no match). Reads only; ranking is decided in `retrieve`."""
        bm25 = self._bm25(query)
        lex_rank = {i: r for r, i in enumerate(sorted(bm25, key=lambda i: -bm25[i]), start=1)}
        sims = None
        if qvec is not None and self.dense and len(qvec) == self.dim:
            sims = np.where(self.has_vec, self.vecs @ qvec, -np.inf)
            dense_rank = {int(i): r for r, i in enumerate(np.argsort(-sims), start=1)}
        out = []
        for c in chunks:
            i = self.pos.get(c.id)
            row = {"chunk_id": c.id, "title": c.title, "page": c.page, "kind": c.kind}
            if i is not None:
                row.update(bm25=round(bm25[i], 2) if i in bm25 else None, bm25_rank=lex_rank.get(i))
                if sims is not None and np.isfinite(sims[i]):
                    row.update(cosine=round(float(sims[i]), 3), cosine_rank=dense_rank[i])
            out.append(row)
        return out

    def first_chunks(self, doc_id: str, k: int) -> list[Chunk]:
        """The opening chunks of one document (used when a query matches nothing in a focused material)."""
        return sorted((c for c in self.chunks if c.doc_id == doc_id), key=lambda c: (c.page, c.id))[:k]

    def problem_chunks(self, doc_id: str, numbers: list[int], k: int = 2) -> list[Chunk]:
        """Chunks of one problem set that contain the statement of "Problem N" for the numbers a student named."""
        out = []
        for n in numbers:
            pat = re.compile(rf"(^|\n)\s*problem\s*0*{n}\b", re.I)
            out += [c for c in self.first_chunks(doc_id, 50) if pat.search(c.text) and c not in out][:1]
        return out[:k]

    def match_problem(self, message: str) -> tuple[Chunk | None, float]:
        """Best problem-set chunk whose text covers most of the message's content words."""
        q = set(tokens(message))
        if len(q) < 8:
            return None, 0.0
        best, best_cov = None, 0.0
        for i, c in enumerate(self.chunks):
            if c.kind != "problem_set":
                continue
            cov = len(q & self.tokset[i]) / len(q)
            if cov > best_cov:
                best, best_cov = c, cov
        return best, best_cov


def solution_chunks_for(pset_id: str, message: str, k: int = 4, exclude_docs: set[str] = frozenset()) -> list[str]:
    """Tutor-only. The most relevant passages of the solutions linked to a problem set, for the checker."""
    q = set(tokens(message))
    with db() as conn:
        rows = conn.execute(
            "SELECT c.text, c.doc_id FROM chunks c JOIN solution_links l ON l.solution_id=c.doc_id "
            "JOIN documents d ON d.id=c.doc_id WHERE l.pset_id=? AND d.status='ready'", (pset_id,)).fetchall()
    rows = [r for r in rows if r["doc_id"] not in exclude_docs]
    scored = sorted(rows, key=lambda r: -len(q & set(tokens(r["text"]))))
    return [r["text"] for r in scored[:k]]
