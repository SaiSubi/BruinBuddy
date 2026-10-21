"""Starter questions for the course home and empty chats (PRD §4.4).

One cheap model call per course whenever its materials change, run in the background. The model only sees short
excerpts of lecture notes and readings, never problem sets, so a starter can't copy a Graded problem."""
import json
import threading

from . import jobs, llm
from .db import db
from .knowledge import natural_key

SOURCE_KINDS = ("lecture_notes", "reading", "class_prep", "other")
MAX_SOURCES = 12

STARTERS_SYSTEM = """You write starter questions for students using an AI tutor in one course. Given titles and short excerpts of the course's lecture notes and readings, write 4 short questions a student in this course might ask: mostly concept questions ("Why…", "What is the difference between…") and one study-guidance question ("What should I review before…"). Each question must be answerable from these materials, under 100 characters, and must not be a homework problem.
Reply with JSON only: {"questions": ["...", "...", "...", "..."]}"""

_inflight: set[int] = set()
_lock = threading.Lock()


def ensure(course_id: int, content_version: int, starter_version: int) -> None:
    """Regenerate in the background if the stored questions are for an older version of the materials."""
    if starter_version == content_version:
        return
    with _lock:
        if course_id in _inflight:
            return
        _inflight.add(course_id)
    jobs.run(_generate, course_id)


def _generate(course_id: int) -> None:
    try:
        with db() as conn:
            course = conn.execute("SELECT content_version FROM courses WHERE id=?", (course_id,)).fetchone()
            docs = conn.execute(
                f"SELECT id, title FROM documents WHERE course_id=? AND status='ready' "
                f"AND kind IN ({','.join('?' * len(SOURCE_KINDS))})", (course_id, *SOURCE_KINDS)).fetchall()
            if not course:
                return
            version = course["content_version"]
            docs = sorted(docs, key=lambda d: natural_key(d["title"]))
            step = max(1, len(docs) // MAX_SOURCES)  # spread the sample across the whole course
            picked = docs[::step][:MAX_SOURCES]
            excerpts = []
            for d in picked:
                row = conn.execute("SELECT text FROM chunks WHERE doc_id=? ORDER BY page, id LIMIT 1", (d["id"],)).fetchone()
                if row:
                    excerpts.append(f"### {d['title']}\n{row['text'][:400]}")
        questions: list[str] = []
        if excerpts:
            raw = llm.complete("starters", [{"role": "system", "content": STARTERS_SYSTEM},
                                            {"role": "user", "content": "\n\n".join(excerpts)}],
                               max_tokens=400, attr={"course_id": course_id})
            got = llm.parse_json(raw).get("questions", [])
            questions = [q.strip() for q in got if isinstance(q, str) and 8 <= len(q.strip()) <= 160][:4]
            if not questions:
                return  # keep the previous set; try again on the next view
        with db() as conn:
            conn.execute("UPDATE courses SET starter_questions=?, starter_version=? WHERE id=?",
                         (json.dumps(questions), version, course_id))
    finally:
        with _lock:
            _inflight.discard(course_id)
