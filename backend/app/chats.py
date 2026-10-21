"""Chats, the streaming message endpoint with its gates, citation sources, and file links."""
import json
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import auth, config, knowledge, storage
from .accounts import current_user
from .courses import Member, allowance, course_tokens, get_member, member_of, pause_state
from .db import db, now
from .materials import file_url
from .tutor import Turn, run_turn

router = APIRouter()

CHAT_KINDS = ("chat", "pset", "review", "quiz")


def _with_urls(citations: list[dict]) -> list[dict]:
    return [{**c, "url": file_url(c["doc_id"], c.get("page"))} for c in citations]


def _own_chat(conn, chat_id: int, user: dict) -> tuple[dict, Member]:
    chat = conn.execute("SELECT * FROM chats WHERE id=? AND user_id=?", (chat_id, user["id"])).fetchone()
    if not chat:
        raise HTTPException(404, "Chat not found")
    return dict(chat), member_of(conn, chat["course_id"], user)


@router.get("/api/courses/{course_id}/chats")
def list_chats(m: Member = Depends(get_member)):
    with db() as conn:
        rows = conn.execute("SELECT id, title, kind, doc_id, updated_at FROM chats WHERE course_id=? AND user_id=? "
                            "ORDER BY updated_at DESC", (m.course["id"], m.user["id"])).fetchall()
    return [dict(r) for r in rows]


class ChatIn(BaseModel):
    kind: str = "chat"
    doc_id: str | None = Field(default=None, max_length=64)


@router.post("/api/courses/{course_id}/chats")
def create_chat(body: ChatIn, m: Member = Depends(get_member)):
    if body.kind not in CHAT_KINDS:
        raise HTTPException(422, "Unknown chat type")
    kb = knowledge.cache.get(m.course["id"])
    doc = kb.docs.get(body.doc_id or "") if body.doc_id else None
    if body.kind == "pset" and not (doc and doc.kind == "problem_set"):
        raise HTTPException(422, "Pick a problem set from this course.")
    if body.kind == "review" and not (doc and kb.is_public(doc.id) and doc.kind not in ("problem_set", "solution")):
        raise HTTPException(422, "Pick a lecture or reading from this course.")
    if body.kind == "quiz" and body.doc_id and not (doc and kb.is_public(doc.id) and doc.id not in kb.graded_psets()):
        raise HTTPException(422, "Pick a topic from this course's lectures and readings.")
    if body.kind == "chat" and body.doc_id:
        raise HTTPException(422, "A free chat has no attached material.")
    title = {"chat": "New chat", "pset": f"{doc.title} help" if doc else "",
             "review": f"Review: {doc.title}" if doc else "",
             "quiz": f"Quiz: {doc.title}" if doc else "Quiz: the course so far"}[body.kind][:80]
    with db() as conn:
        cur = conn.execute("INSERT INTO chats(course_id,user_id,title,kind,doc_id,is_preview,created_at,updated_at) "
                           "VALUES(?,?,?,?,?,?,?,?) RETURNING id",
                           (m.course["id"], m.user["id"], title, body.kind, doc.id if doc else None,
                            int(m.is_staff), now(), now()))
        chat_id = cur.fetchone()["id"]
    return {"id": chat_id, "title": title, "kind": body.kind, "doc_id": doc.id if doc else None}


@router.get("/api/chats/{chat_id}")
def get_chat(chat_id: int, user: dict = Depends(current_user)):
    with db() as conn:
        chat, m = _own_chat(conn, chat_id, user)
        rows = conn.execute("SELECT id, role, content, citations, memory_used, problem_doc_id FROM messages "
                            "WHERE chat_id=? ORDER BY id", (chat_id,)).fetchall()
    kb = knowledge.cache.get(chat["course_id"])
    last_problem = next((r["problem_doc_id"] for r in reversed(rows) if r["role"] == "user" and r["problem_doc_id"]), None)
    msgs = [{"id": r["id"], "role": r["role"], "content": r["content"], "citations": _with_urls(json.loads(r["citations"])),
             "memory_used": json.loads(r["memory_used"])} for r in rows]
    return {"id": chat["id"], "course_id": chat["course_id"], "title": chat["title"], "kind": chat["kind"],
            "doc_id": chat["doc_id"], "is_preview": bool(chat["is_preview"]), "messages": msgs,
            "rule": kb.rule(chat["doc_id"] if chat["kind"] == "pset" else last_problem)}


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


def _limit(status: int, message: str, until: float | None = None):
    raise HTTPException(status, {"message": message, "until": until})


@router.post("/api/chats/{chat_id}/messages")
def post_message(chat_id: int, body: MessageIn, user: dict = Depends(current_user)):
    text = body.content.strip()
    if not text:
        raise HTTPException(422, "Type a question first.")
    with db() as conn:
        chat, m = _own_chat(conn, chat_id, user)
    c = m.course
    if c["status"] != "active":
        raise HTTPException(409, "This course isn't active yet.")
    kb = knowledge.cache.get(c["id"])  # outside the connection above: building an index opens its own
    if not kb.has_material:
        raise HTTPException(409, "Your instructor hasn't added course materials yet, so the tutor isn't open.")
    with db() as conn:
        pause = pause_state(conn, c["id"])
        if pause["active"]:
            _limit(423, pause["message"] or "The tutor is paused by your instructor.", pause["until"])
        if m.role == "student":
            a = allowance(conn, c, user["id"])
            if a["reached"]:
                _limit(429, f"You've used your tutor allowance for this {a['period']}.", a["frees_at"])
        if course_tokens(conn, c) >= c["token_ceiling"]:
            _limit(429, "This course has used its plan's AI allowance. Let your instructor know.")
        day = conn.execute("SELECT COUNT(*) AS n FROM messages WHERE role='user' AND created_at>?",
                           (time.time() - 86400,)).fetchone()["n"]
        if day >= config.GLOBAL_DAILY_LIMIT:
            _limit(429, "BruinBuddy has reached its daily limit for everyone. Please try again tomorrow.")

    turn = Turn(course=c, user_id=user["id"], chat=chat, is_preview=bool(chat["is_preview"]))

    def events():
        for ev in run_turn(kb, turn, text):
            if ev["type"] == "done":
                ev["message"]["citations"] = _with_urls(ev["message"]["citations"])
            yield f"data: {json.dumps(ev)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/api/sources/{chunk_id}")
def get_source(chunk_id: int, user: dict = Depends(current_user)):
    with db() as conn:
        row = conn.execute("SELECT c.doc_id, d.course_id FROM chunks c JOIN documents d ON d.id=c.doc_id WHERE c.id=?",
                           (chunk_id,)).fetchone()
        if not row or row["course_id"] is None:
            raise HTTPException(404, "Source not found")
        member_of(conn, row["course_id"], user)
    c = knowledge.cache.get(row["course_id"]).index.by_id.get(chunk_id)  # the index holds public chunks only
    if not c:
        raise HTTPException(404, "Source not found")
    return {"chunk_id": c.id, "doc_id": c.doc_id, "title": c.title, "page": c.page, "text": c.text,
            "url": file_url(c.doc_id, c.page)}


@router.get("/files/{doc_id}")
def get_file(doc_id: str, t: str = Query(default="")):
    scope = auth.verify_file_token(doc_id, t)
    if not scope:
        raise HTTPException(403, "This link has expired. Go back and open the document again.")
    with db() as conn:
        doc = conn.execute("SELECT course_id, file_name, storage_path, content_type FROM documents WHERE id=?",
                           (doc_id,)).fetchone()
    if not doc or doc["course_id"] is None:
        raise HTTPException(404, "Not found")
    if scope != "s" and not knowledge.cache.get(doc["course_id"]).is_public(doc_id):
        raise HTTPException(404, "Not found")  # e.g. a solution whose problem set isn't open
    media = doc["content_type"] or "application/pdf"
    if storage.configured():  # production: send the browser to a short-lived Supabase Storage link
        try:
            url = storage.signed_url(doc["storage_path"] or doc["file_name"])
        except storage.NotFound:
            raise HTTPException(404, "This file isn't available to open. Its text is shown in the source panel.")
        except (httpx.HTTPError, KeyError):
            raise HTTPException(502, "File storage is unavailable")
        return RedirectResponse(url, status_code=302, headers={"Cache-Control": "no-store"})
    try:
        path = storage.local_path(doc["storage_path"], doc["file_name"])
    except storage.NotFound:
        raise HTTPException(404, "Not found")
    if not path.exists():
        raise HTTPException(404, "This file isn't available to open. Its text is shown in the source panel.")
    return FileResponse(path, media_type=media)
