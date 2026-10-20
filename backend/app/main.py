"""FastAPI app: sign-in, chats, streaming messages, sources, files, dashboard.

Auth is a signed bearer token (see auth.py).  Sign-in is name + role, optionally gated by access codes.
This is demo-grade identity: anyone who knows the access code can claim any student name."""
import json
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import httpx

from . import auth, config, storage
from .db import db, init_db, now
from .guard import LeakGuard
from .retrieval import Index
from .tutor import run_turn

state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.check_production_settings()
    init_db()
    state["index"] = Index()
    state["guard"] = LeakGuard()
    yield


app = FastAPI(title="BruinBuddy", lifespan=lifespan,
              docs_url=None if config.PRODUCTION else "/docs", redoc_url=None, openapi_url=None if config.PRODUCTION else "/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS, allow_methods=["GET", "POST", "DELETE"],
                   allow_headers=["Authorization", "Content-Type"], max_age=600)


class SessionIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    role: str = Field(pattern="^(student|professor)$")
    code: str = Field(default="", max_length=200)


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


def current_user(authorization: str | None = Header(default=None)) -> dict:
    token = authorization[7:] if authorization and authorization.lower().startswith("bearer ") else ""
    user_id = auth.verify_session_token(token)
    if user_id:
        with db() as conn:
            row = conn.execute("SELECT id, name, role FROM users WHERE id=?", (user_id,)).fetchone()
        if row:
            return dict(row)
    raise HTTPException(401, "Not signed in")


def student(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "student":
        raise HTTPException(403, "Students only")
    return user


def professor(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "professor":
        raise HTTPException(403, "Professors only")
    return user


def _own_chat(conn, chat_id: int, user_id: int):
    chat = conn.execute("SELECT * FROM chats WHERE id=? AND user_id=?", (chat_id, user_id)).fetchone()
    if not chat:
        raise HTTPException(404, "Chat not found")
    return chat


def _with_urls(citations: list[dict]) -> list[dict]:
    return [{**c, "url": f"/files/{c['doc_id']}?t={auth.make_file_token(c['doc_id'])}#page={c['page']}"}
            for c in citations]


def _count_questions(conn, since: float, user_id: int | None = None) -> int:
    if user_id is None:
        row = conn.execute("SELECT COUNT(*) AS n FROM messages WHERE role='user' AND created_at>?", (since,)).fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) AS n FROM messages m JOIN chats c ON c.id=m.chat_id "
                           "WHERE m.role='user' AND c.user_id=? AND m.created_at>?", (user_id, since)).fetchone()
    return row["n"]


@app.get("/api/config")
def public_config():
    return {"student_code_required": bool(config.STUDENT_CODE),
            "professor_code_required": bool(config.PROFESSOR_CODE),
            "professor_enabled": bool(config.PROFESSOR_CODE) or not config.PRODUCTION}


@app.post("/api/session")
def sign_in(body: SessionIn):
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "Name required")
    required = config.STUDENT_CODE if body.role == "student" else config.PROFESSOR_CODE
    if body.role == "professor" and config.PRODUCTION and not required:
        raise HTTPException(403, "Professor sign-in is not enabled")
    if required and not auth.codes_equal(body.code, required):
        raise HTTPException(403, "Wrong access code")
    with db() as conn:
        conn.execute("INSERT INTO users(name,role,created_at) VALUES(?,?,?) ON CONFLICT(name, role) DO NOTHING",
                     (name, body.role, now()))
        user = conn.execute("SELECT id, name, role FROM users WHERE name=? AND role=?", (name, body.role)).fetchone()
    return {**dict(user), "token": auth.make_session_token(user["id"])}


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    return user


@app.get("/api/chats")
def list_chats(user: dict = Depends(student)):
    with db() as conn:
        rows = conn.execute("SELECT id, title, updated_at FROM chats WHERE user_id=? ORDER BY updated_at DESC",
                            (user["id"],)).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/chats")
def create_chat(user: dict = Depends(student)):
    with db() as conn:
        cur = conn.execute("INSERT INTO chats(user_id,title,created_at,updated_at) VALUES(?,?,?,?) RETURNING id",
                           (user["id"], "New chat", now(), now()))
        return {"id": cur.fetchone()["id"], "title": "New chat"}


@app.get("/api/chats/{chat_id}")
def get_chat(chat_id: int, user: dict = Depends(student)):
    with db() as conn:
        chat = _own_chat(conn, chat_id, user["id"])
        rows = conn.execute("SELECT id, role, content, citations, memory_used FROM messages WHERE chat_id=? ORDER BY id",
                            (chat_id,)).fetchall()
    msgs = [{**dict(r), "citations": _with_urls(json.loads(r["citations"])), "memory_used": json.loads(r["memory_used"])}
            for r in rows]
    return {"id": chat["id"], "title": chat["title"], "messages": msgs}


@app.post("/api/chats/{chat_id}/messages")
def post_message(chat_id: int, body: MessageIn, user: dict = Depends(student)):
    day_ago = time.time() - 24 * 3600
    with db() as conn:
        _own_chat(conn, chat_id, user["id"])
        if _count_questions(conn, day_ago, user["id"]) >= config.DAILY_MESSAGE_LIMIT:
            raise HTTPException(429, f"Daily limit of {config.DAILY_MESSAGE_LIMIT} questions reached. Try again tomorrow.")
        if _count_questions(conn, day_ago) >= config.GLOBAL_DAILY_LIMIT:
            raise HTTPException(429, "The demo has reached its daily limit. Please try again tomorrow.")

    def events():
        for ev in run_turn(state["index"], state["guard"], user["id"], chat_id, body.content.strip()):
            if ev["type"] == "done":
                ev["message"]["citations"] = _with_urls(ev["message"]["citations"])
            yield f"data: {json.dumps(ev)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/sources/{chunk_id}")
def get_source(chunk_id: int, user: dict = Depends(current_user)):
    c = state["index"].by_id.get(chunk_id)  # index holds public chunks only
    if not c:
        raise HTTPException(404, "Source not found")
    return {"chunk_id": c.id, "doc_id": c.doc_id, "title": c.title, "page": c.page, "text": c.text,
            "url": _with_urls([{"doc_id": c.doc_id, "page": c.page}])[0]["url"]}


@app.get("/files/{doc_id}")
def get_file(doc_id: str, t: str = Query(default="")):
    if not auth.verify_file_token(doc_id, t):
        raise HTTPException(403, "Link expired or invalid")
    with db() as conn:
        row = conn.execute("SELECT file_name FROM documents WHERE id=? AND tutor_only=0", (doc_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Not found")
    if storage.configured():  # production: send the browser to a short-lived Supabase Storage link
        try:
            return RedirectResponse(storage.signed_url(row["file_name"]), status_code=302,
                                    headers={"Cache-Control": "no-store"})
        except (httpx.HTTPError, KeyError):
            raise HTTPException(502, "File storage is unavailable")
    path = config.PDF_DIR / row["file_name"]  # local dev
    if not path.exists():
        raise HTTPException(404, "Not found")
    return FileResponse(path, media_type="application/pdf")


@app.get("/api/dashboard")
def dashboard(user: dict = Depends(professor)):
    with db() as conn:
        return {"questions_asked": _count_questions(conn, 0)}


@app.get("/api/health")
def health():
    return {"ok": True, "llm": "mock" if config.MOCK_LLM else ("ready" if config.OPENROUTER_API_KEY else "no_key"),
            "public_chunks": len(state["index"].chunks)}


if config.FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIST, html=True), name="frontend")
