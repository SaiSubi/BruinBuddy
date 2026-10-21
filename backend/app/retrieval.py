"""BM25 retrieval over one course's public chunks, plus the one helper that touches tutor-only solutions.

An `Index` only ever holds chunks students may see (knowledge.py decides which). Protected solution chunks are
reachable only through `solution_chunks_for`, which feeds the checker and is never shown to the tutor.
"""
import math
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass

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

    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        self.by_id = {c.id: c for c in chunks}
        self.tok = [tokens((c.title + " ") * 3 + c.text) for c in chunks]
        self.dl = [len(t) for t in self.tok]
        self.avgdl = (sum(self.dl) / len(self.dl)) if self.dl else 1.0
        self.post: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for i, t in enumerate(self.tok):
            for term, tf in Counter(t).items():
                self.post[term].append((i, tf))
        self.n = len(chunks)
        self.tokset = [set(t) for t in self.tok]

    def search(self, query: str, k: int = 6, *, exclude_docs: set[str] | frozenset = frozenset(),
               only_docs: set[str] | None = None) -> list[tuple[float, Chunk]]:
        scores: dict[int, float] = defaultdict(float)
        for term in set(tokens(query)):
            plist = self.post.get(term)
            if not plist:
                continue
            idf = math.log(1 + (self.n - len(plist) + 0.5) / (len(plist) + 0.5))
            for i, tf in plist:
                norm = tf + self.k1 * (1 - self.b + self.b * self.dl[i] / self.avgdl)
                scores[i] += idf * tf * (self.k1 + 1) / norm
        out = []
        for i, s in sorted(scores.items(), key=lambda kv: -kv[1]):
            c = self.chunks[i]
            if c.doc_id in exclude_docs or (only_docs is not None and c.doc_id not in only_docs):
                continue
            out.append((s, c))
            if len(out) >= k:
                break
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
