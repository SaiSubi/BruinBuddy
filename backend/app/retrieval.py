"""BM25 retrieval over public chunks, plus helpers that touch tutor-only solutions.

Only `Index` (public chunks) is ever used to produce citations or tutor context.
Solution chunks are reachable only through `solution_chunks_for`, which feeds the checker.
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
    file_name: str
    page: int
    text: str


class Index:
    k1, b = 1.5, 0.75

    def __init__(self) -> None:
        with db() as conn:
            rows = conn.execute(
                "SELECT c.id, c.doc_id, d.title, d.kind, d.file_name, c.page, c.text FROM chunks c "
                "JOIN documents d ON d.id=c.doc_id WHERE c.tutor_only=0 AND d.tutor_only=0").fetchall()
        self.chunks = [Chunk(id=r["id"], doc_id=r["doc_id"], title=r["title"], kind=r["kind"],
                             file_name=r["file_name"], page=r["page"], text=r["text"]) for r in rows]
        self.by_id = {c.id: c for c in self.chunks}
        self.tok = [tokens((c.title + " ") * 3 + c.text) for c in self.chunks]
        self.dl = [len(t) for t in self.tok]
        self.avgdl = (sum(self.dl) / len(self.dl)) if self.dl else 1.0
        self.post: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for i, t in enumerate(self.tok):
            for term, tf in Counter(t).items():
                self.post[term].append((i, tf))
        self.n = len(self.chunks)
        self.tokset = [set(t) for t in self.tok]

    def search(self, query: str, k: int = 6, kinds: set[str] | None = None) -> list[tuple[float, Chunk]]:
        scores: dict[int, float] = defaultdict(float)
        for term in set(tokens(query)):
            plist = self.post.get(term)
            if not plist:
                continue
            idf = math.log(1 + (self.n - len(plist) + 0.5) / (len(plist) + 0.5))
            for i, tf in plist:
                norm = tf + self.k1 * (1 - self.b + self.b * self.dl[i] / self.avgdl)
                scores[i] += idf * tf * (self.k1 + 1) / norm
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])
        out = []
        for i, s in ranked:
            c = self.chunks[i]
            if kinds and c.kind not in kinds:
                continue
            out.append((s, c))
            if len(out) >= k:
                break
        return out

    # ---- assigned-problem detection -------------------------------------------------
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

    def problem_doc_from_reference(self, message: str) -> str | None:
        """'pset 4', 'problem set 04', 'class 7 problem' -> doc id of that problem set."""
        m = message.lower()
        hit = re.search(r"(?:pset|problem\s*set|homework|hw)\s*#?\s*(\d{1,2})", m)
        name = None
        if hit:
            name = f"pset{int(hit.group(1)):02d}.pdf"
        else:
            hit = re.search(r"class\s*#?\s*(\d{1,2})\s*(?:in[- ]class\s*)?(?:problem|pset)", m)
            if hit:
                name = f"class{int(hit.group(1)):02d}_pset.pdf"
        if not name:
            return None
        with db() as conn:
            row = conn.execute("SELECT id FROM documents WHERE file_name LIKE ? AND kind='problem_set'",
                               (f"%{name}",)).fetchone()
        return row["id"] if row else None


def solution_chunks_for(problem_doc_id: str, message: str, k: int = 4) -> list[str]:
    """Tutor-only. Returns the most relevant solution passages for the checker. Never shown to the tutor."""
    q = set(tokens(message))
    with db() as conn:
        rows = conn.execute(
            "SELECT c.text FROM chunks c JOIN documents d ON d.id=c.doc_id "
            "WHERE d.tutor_only=1 AND d.linked_doc_id=?", (problem_doc_id,)).fetchall()
    scored = sorted(rows, key=lambda r: -len(q & set(tokens(r["text"]))))
    return [r["text"] for r in scored[:k]]
