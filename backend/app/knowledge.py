"""Per-course knowledge: which materials students may see right now, a BM25 index over them, and a leak guard
over the solutions they may not see.

Cached per course and rebuilt when the course's `content_version` (bumped on uploads, deletes, re-categorising,
relinking and mode changes), its `index_version` (bumped when chunk embeddings are filled in) or its set of open
problem sets (which also changes when a release date passes) differs from the cached copy. All are read from the
database on every turn, so this works across processes. A build that finds chunks without a current embedding
starts a background backfill (embeddings.py).
"""
import re
import threading
import time
from dataclasses import dataclass, field

from . import embeddings, llm
from .db import db
from .guard import LeakGuard
from .retrieval import Chunk, Index

MODES = ("graded", "practice", "open")
MODE_RANK = {"graded": 0, "practice": 1, "open": 2}  # strictest first
MODE_LABELS = {"graded": "Graded: hints only", "practice": "Practice: full help", "open": "Solutions open"}
PUBLIC_KINDS = ("lecture_notes", "reading", "class_prep", "other", "problem_set")
KINDS = PUBLIC_KINDS + ("solution",)
KIND_LABELS = {"lecture_notes": "Lecture notes", "reading": "Reading", "class_prep": "Class prep",
               "other": "Other", "problem_set": "Problem set", "solution": "Solution"}


def effective_mode(mode: str | None, release_at: float | None, at: float | None = None) -> str:
    if mode == "open" or (release_at is not None and release_at <= (at or time.time())):
        return "open"
    return mode if mode in MODES else "graded"


def natural_key(title: str) -> list:
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", title)]


def bump_content(conn, course_id: int) -> None:
    conn.execute("UPDATE courses SET content_version=content_version+1 WHERE id=?", (course_id,))


@dataclass
class Doc:
    id: str
    title: str
    kind: str
    mode: str            # effective mode (problem sets only)
    set_mode: str        # the mode staff chose
    release_at: float | None
    confirm_answers: bool
    links: list[str] = field(default_factory=list)  # solution -> problem sets it covers; problem set -> its solutions


# "pset 4", "problem set 04", "homework 3", "HW3", "assignment 2b"
_SET_REF = re.compile(r"\b(?:problem\s*sets?|psets?|homeworks?|hw|assignments?)\s*#?\s*0*(\d{1,3})([a-z]?)\b", re.I)
# "class 7 problems", "class 5a in-class problem" (in messages); "Class 07: Problems" (in titles)
_CLASS_REF_MSG = re.compile(r"\bclass\s*#?\s*0*(\d{1,3})([a-z]?)\s*(?:in[- ]class\s*)?(?:problems?|psets?)\b", re.I)
_CLASS_REF_TITLE = re.compile(r"\bclass\s*#?\s*0*(\d{1,3})([a-z]?)\b", re.I)


def _message_refs(text: str) -> list[tuple[str, int, str]]:
    refs = [("set", int(m.group(1)), m.group(2).lower()) for m in _SET_REF.finditer(text)]
    refs += [("class", int(m.group(1)), m.group(2).lower()) for m in _CLASS_REF_MSG.finditer(text)]
    return refs


def _title_refs(title: str) -> set[tuple[str, int, str]]:
    refs = {("set", int(m.group(1)), m.group(2).lower()) for m in _SET_REF.finditer(title)}
    refs |= {("class", int(m.group(1)), m.group(2).lower()) for m in _CLASS_REF_TITLE.finditer(title)}
    return refs


@dataclass
class CourseKnowledge:
    course_id: int
    key: tuple
    docs: dict[str, Doc]   # ready documents of the course
    public: set[str]       # ids of documents students may see, retrieve, cite and open
    guarded: set[str]      # solutions that cover a Graded set (or no set): never used to explain anything
    index: Index
    guard: LeakGuard
    unembedded: int = 0    # ready chunks (public or not) without a vector from the current embedding model

    @property
    def has_material(self) -> bool:
        return bool(self.public)

    def is_public(self, doc_id: str) -> bool:
        return doc_id in self.public

    def psets(self) -> list[Doc]:
        return sorted((d for d in self.docs.values() if d.kind == "problem_set"), key=lambda d: natural_key(d.title))

    def graded_psets(self) -> set[str]:
        return {d.id for d in self.docs.values() if d.kind == "problem_set" and d.mode == "graded"}

    def rule(self, pset_id: str | None) -> dict | None:
        d = self.docs.get(pset_id or "")
        if not d or d.kind != "problem_set":
            return None
        return {"doc_id": d.id, "title": d.title, "mode": d.mode, "label": MODE_LABELS[d.mode],
                "confirm_answers": d.confirm_answers}

    def psets_from_references(self, text: str) -> list[str]:
        """Problem sets named in a message: "pset 4", "homework 3", "class 7 problems"."""
        found: list[str] = []
        sets = [(d, _title_refs(d.title)) for d in self.psets()]
        for kind, n, letter in _message_refs(text):
            exact = [d for d, tr in sets if (kind, n, letter) in tr]
            if not exact and not letter:  # "class 5 problems" when only "Class 05a" exists
                exact = [d for d, tr in sets if any(k == kind and m == n for k, m, _ in tr)]
            if len(exact) == 1 and exact[0].id not in found:
                found.append(exact[0].id)
        return found

    def _psets_in(self, text: str) -> list[str]:
        found = self.psets_from_references(text)
        chunk, cov = self.index.match_problem(text)
        if chunk and cov >= 0.6 and chunk.doc_id not in found:
            found.append(chunk.doc_id)
        return found

    def turn_pset(self, message: str, prior_user_msgs: list[str], attached: str | None = None) -> str | None:
        """The problem set whose rule applies to this turn. Candidates are the chat's attached set, sets the message
        names, and a set whose text it pastes; if the message brings none, the last few student messages are checked
        (v0 behaviour). When several apply, the strictest mode wins, so naming a Practice set can't unlock a pasted
        Graded problem."""
        ids = ([attached] if attached in self.docs else []) + self._psets_in(message)
        if len(ids) == (1 if attached in self.docs else 0):
            for text in reversed(prior_user_msgs[-3:]):
                more = self._psets_in(text)
                if more:
                    ids += more
                    break
        ids = [i for i in dict.fromkeys(ids) if i in self.docs and self.docs[i].kind == "problem_set"]
        return min(ids, key=lambda i: MODE_RANK[self.docs[i].mode]) if ids else None


def _build(course_id: int, key: tuple) -> CourseKnowledge:
    open_psets = key[1]
    with db() as conn:
        drows = conn.execute("SELECT id, title, kind, mode, release_at, confirm_answers FROM documents "
                             "WHERE course_id=? AND status='ready'", (course_id,)).fetchall()
        lrows = conn.execute("SELECT l.solution_id, l.pset_id FROM solution_links l JOIN documents d "
                             "ON d.id=l.solution_id WHERE d.course_id=?", (course_id,)).fetchall()
        crows = conn.execute("SELECT c.id, c.doc_id, c.page, c.text, c.embedding, c.embed_model FROM chunks c "
                             "JOIN documents d ON d.id=c.doc_id WHERE d.course_id=? AND d.status='ready'",
                             (course_id,)).fetchall()
    at = time.time()
    docs = {r["id"]: Doc(id=r["id"], title=r["title"], kind=r["kind"],
                         mode=effective_mode(r["mode"], r["release_at"], at), set_mode=r["mode"] or "graded",
                         release_at=r["release_at"], confirm_answers=bool(r["confirm_answers"])) for r in drows}
    raw_links: dict[str, list[str]] = {}
    for r in lrows:
        raw_links.setdefault(r["solution_id"], []).append(r["pset_id"])
        if r["solution_id"] in docs and r["pset_id"] in docs:
            docs[r["solution_id"]].links.append(r["pset_id"])
            docs[r["pset_id"]].links.append(r["solution_id"])

    public, guarded = set(), set()
    for d in docs.values():
        if d.kind != "solution":
            public.add(d.id)
            continue
        linked = raw_links.get(d.id, [])  # includes problem sets that are not ready: they count as closed
        if linked and all(p in open_psets for p in linked):
            public.add(d.id)
        elif not linked or any(docs[p].mode == "graded" if p in docs else True for p in linked):
            guarded.add(d.id)  # solutions linked only to Practice sets may be explained, so they are not guarded

    model = llm.embed_model()
    crows = [r for r in crows if r["doc_id"] in docs]
    vectors = {r["id"]: embeddings.from_blob(r["embedding"]) for r in crows
               if r["embedding"] is not None and r["embed_model"] == model}
    chunks = [Chunk(id=r["id"], doc_id=r["doc_id"], title=docs[r["doc_id"]].title, kind=docs[r["doc_id"]].kind,
                    page=r["page"], text=r["text"]) for r in crows]
    shown = [c for c in chunks if c.doc_id in public]
    index = Index(shown, [vectors.get(c.id) for c in shown])
    guard = LeakGuard((c.text for c in chunks if c.doc_id in guarded), (c.text for c in chunks if c.doc_id in public))
    return CourseKnowledge(course_id=course_id, key=key, docs=docs, public=public, guarded=guarded, index=index,
                           guard=guard, unembedded=len(chunks) - len(vectors))


class KnowledgeCache:
    def __init__(self) -> None:
        self._cache: dict[int, CourseKnowledge] = {}
        self._locks: dict[int, threading.Lock] = {}
        self._guard = threading.Lock()

    @staticmethod
    def _key(course_id: int) -> tuple:
        with db() as conn:
            row = conn.execute("SELECT content_version, index_version FROM courses WHERE id=?", (course_id,)).fetchone()
            rows = conn.execute("SELECT id FROM documents WHERE course_id=? AND kind='problem_set' AND status='ready' "
                                "AND (mode='open' OR (release_at IS NOT NULL AND release_at<=?))",
                                (course_id, time.time())).fetchall()
        return (row["content_version"] if row else -1, frozenset(r["id"] for r in rows),
                row["index_version"] if row else -1)

    def get(self, course_id: int) -> CourseKnowledge:
        key = self._key(course_id)
        kb = self._cache.get(course_id)
        if kb and kb.key == key:
            return kb
        with self._guard:
            lock = self._locks.setdefault(course_id, threading.Lock())
        with lock:
            kb = self._cache.get(course_id)
            if not (kb and kb.key == key):
                kb = _build(course_id, key)
                self._cache[course_id] = kb
        if kb.unembedded:
            embeddings.schedule_backfill(course_id, key)
        return kb


cache = KnowledgeCache()
