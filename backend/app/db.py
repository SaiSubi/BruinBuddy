"""Database access.  SQLite for local dev (default), Postgres (Supabase) when DATABASE_URL is set.

SQL in this codebase is written in the subset both accept: `?` placeholders (translated for Postgres),
`INSERT ... ON CONFLICT`, and `RETURNING id`.  Rows support `row["col"]` and `dict(row)` on both.
"""
import sqlite3
import time
from contextlib import contextmanager

from . import config

TABLES = ["users", "chats", "messages", "memories", "documents", "chunks", "usage_log"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id {PK}, name TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('student','professor')),
  created_at DOUBLE PRECISION NOT NULL, UNIQUE(name, role));
CREATE TABLE IF NOT EXISTS chats(
  id {PK}, user_id INTEGER NOT NULL REFERENCES users(id), title TEXT NOT NULL,
  created_at DOUBLE PRECISION NOT NULL, updated_at DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS messages(
  id {PK}, chat_id INTEGER NOT NULL REFERENCES chats(id),
  role TEXT NOT NULL CHECK(role IN ('user','assistant')), content TEXT NOT NULL,
  citations TEXT NOT NULL DEFAULT '[]', memory_used TEXT NOT NULL DEFAULT '[]', created_at DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS memories(
  id {PK}, user_id INTEGER NOT NULL REFERENCES users(id), text TEXT NOT NULL,
  created_at DOUBLE PRECISION NOT NULL, updated_at DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS documents(
  id TEXT PRIMARY KEY, title TEXT NOT NULL, kind TEXT NOT NULL, file_name TEXT NOT NULL,
  file_hash TEXT NOT NULL, tutor_only INTEGER NOT NULL DEFAULT 0, linked_doc_id TEXT, license TEXT);
CREATE TABLE IF NOT EXISTS chunks(
  id {PK}, doc_id TEXT NOT NULL REFERENCES documents(id), page INTEGER NOT NULL,
  text TEXT NOT NULL, tutor_only INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_chats_user ON chats(user_id);
CREATE TABLE IF NOT EXISTS usage_log(
  id {PK}, ts DOUBLE PRECISION NOT NULL, purpose TEXT NOT NULL, model TEXT NOT NULL,
  prompt_tokens INTEGER, completion_tokens INTEGER, cost DOUBLE PRECISION)
"""

IS_PG = bool(config.DATABASE_URL)
_pool = None


class _Conn:
    """Thin wrapper so call sites use `?` placeholders on both backends."""

    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql: str, params=()):
        if IS_PG:
            return self.raw.execute(sql.replace("?", "%s"), params)
        return self.raw.execute(sql, params)


def _get_pool():
    global _pool
    if _pool is None:
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool
        # prepare_threshold=None: required behind Supabase's transaction pooler (pgbouncer)
        _pool = ConnectionPool(config.DATABASE_URL, min_size=1, max_size=8, open=True,
                               kwargs={"row_factory": dict_row, "prepare_threshold": None})
    return _pool


@contextmanager
def db():
    if IS_PG:
        with _get_pool().connection() as raw:  # commits on success, rolls back on error
            yield _Conn(raw)
        return
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    raw = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    raw.row_factory = sqlite3.Row
    raw.execute("PRAGMA foreign_keys=ON")
    try:
        yield _Conn(raw)
        raw.commit()
    finally:
        raw.close()


def init_db() -> None:
    pk = "BIGSERIAL PRIMARY KEY" if IS_PG else "INTEGER PRIMARY KEY"
    statements = [s.strip() for s in SCHEMA.replace("{PK}", pk).split(";") if s.strip()]
    with db() as conn:
        for st in statements:
            conn.execute(st)
        if IS_PG:
            # Supabase exposes the public schema through its REST API. Enabling RLS with no policies
            # denies the anon/authenticated roles everything; this backend connects as a bypass role.
            for t in TABLES:
                conn.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")


def now() -> float:
    return time.time()
