"""Chunk embeddings for hybrid retrieval (retrieval.py).

Each chunk is embedded once, with a short header naming its material ("Reading: Reading 3: …, p. 2"), which helps a
passage match questions about its topic. Vectors are stored on the chunk with the model that made them. Uploads
embed before their chunks are saved; chunks without a current vector (older data, a failed call, a model change)
are filled in by a background backfill, which bumps the course's `index_version` so its index is rebuilt.
A chunk without a vector is still found by BM25.
"""
import logging
import threading

import numpy as np

from . import jobs, llm
from .db import db

log = logging.getLogger("bruinbuddy.embeddings")

_inflight: set[int] = set()
_tried: dict[int, tuple] = {}  # course -> knowledge key a backfill was last started for (no retry loops)
_lock = threading.Lock()


def chunk_text(title: str, kind: str, page: int, text: str) -> str:
    from .knowledge import KIND_LABELS
    return f"{KIND_LABELS.get(kind, kind)}: {title}, p. {page}\n\n{text}"


def unit(v) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32)
    n = float(np.linalg.norm(v))
    return v / n if n else v


def to_blob(v) -> bytes:
    return unit(v).tobytes()


def from_blob(b) -> np.ndarray:
    return np.frombuffer(bytes(b), dtype=np.float32)


def embed_texts(texts: list[str], attr: dict | None) -> list[bytes] | None:
    """Stored vectors for these texts, or None if embeddings are unavailable (the caller saves the chunks anyway)."""
    if not texts:
        return []
    if not llm.can_embed():
        return None
    try:
        return [to_blob(v) for v in llm.embed("embed", texts, attr=attr)]
    except Exception:
        log.exception("embedding %d texts failed", len(texts))
        return None


def query_vector(query: str, attr: dict) -> np.ndarray | None:
    """The question's vector, or None (the turn then uses BM25 alone)."""
    try:
        return unit(llm.embed("embed_query", [query], attr=attr)[0])
    except Exception:
        log.exception("embedding a query failed")
        return None


def schedule_backfill(course_id: int, key: tuple) -> None:
    if not llm.can_embed():
        return
    with _lock:
        if course_id in _inflight or _tried.get(course_id) == key:
            return
        _inflight.add(course_id)
        _tried[course_id] = key
    jobs.run(backfill, course_id)


def backfill(course_id: int) -> int:
    """Embed the course's chunks that lack a vector from the current model. Returns how many were filled."""
    model, filled = llm.embed_model(), 0
    try:
        with db() as conn:
            rows = conn.execute(
                "SELECT c.id, c.page, c.text, d.title, d.kind FROM chunks c JOIN documents d ON d.id=c.doc_id "
                "WHERE d.course_id=? AND d.status='ready' AND (c.embedding IS NULL OR c.embed_model IS NULL "
                "OR c.embed_model<>?) ORDER BY c.id", (course_id, model)).fetchall()
        for i in range(0, len(rows), 256):
            batch = rows[i:i + 256]
            blobs = embed_texts([chunk_text(r["title"], r["kind"], r["page"], r["text"]) for r in batch],
                                {"course_id": course_id})
            if blobs is None:
                break
            with db() as conn:
                for r, b in zip(batch, blobs):
                    conn.execute("UPDATE chunks SET embedding=?, embed_model=? WHERE id=?", (b, model, r["id"]))
            filled += len(batch)
        if filled:
            with db() as conn:
                conn.execute("UPDATE courses SET index_version=index_version+1 WHERE id=?", (course_id,))
    finally:
        with _lock:
            _inflight.discard(course_id)
    return filled
