"""Database access.  SQLite for local dev (default), Postgres (Supabase) when DATABASE_URL is set.

SQL in this codebase is written in the subset both accept: `?` placeholders (translated for Postgres),
`INSERT ... ON CONFLICT`, and `RETURNING id`.  Rows support `row["col"]` and `dict(row)` on both.

`init_db()` is safe to run on every start: it upgrades a v0 database in place (see `_archive_v0`), creates
missing tables, and adds columns introduced since v0.
"""
import sqlite3
import time
from contextlib import contextmanager

from . import config

TABLES = ["users", "courses", "memberships", "staff_codes", "documents", "solution_links", "chunks", "guidelines",
          "pauses", "chats", "messages", "illustrations", "memories", "usage_log", "stripe_events"]
V0_CONVERSATION_TABLES = ["users", "chats", "messages", "memories"]  # replaced in v1; archived as v0_*

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id {PK}, auth_id TEXT NOT NULL UNIQUE, email TEXT NOT NULL, name TEXT NOT NULL,
  password_hash TEXT, account_type TEXT NOT NULL DEFAULT 'instructor',
  is_sample INTEGER NOT NULL DEFAULT 0, created_at DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS courses(
  id {PK}, name TEXT NOT NULL, slug TEXT UNIQUE, owner_id INTEGER NOT NULL REFERENCES users(id),
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','active')),
  student_seats INTEGER NOT NULL, staff_seats INTEGER NOT NULL, token_cap INTEGER NOT NULL,
  cap_period TEXT NOT NULL DEFAULT 'week', token_ceiling BIGINT NOT NULL, price_cents INTEGER NOT NULL,
  student_code TEXT UNIQUE, code_expires_at DOUBLE PRECISION, email_domain TEXT,
  general_guideline TEXT NOT NULL DEFAULT '', starter_questions TEXT NOT NULL DEFAULT '[]',
  starter_version INTEGER NOT NULL DEFAULT -1, content_version INTEGER NOT NULL DEFAULT 0,
  setup TEXT NOT NULL DEFAULT '{}', stripe_session_id TEXT, paid_at DOUBLE PRECISION,
  created_at DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS memberships(
  id {PK}, course_id INTEGER NOT NULL REFERENCES courses(id), user_id INTEGER NOT NULL REFERENCES users(id),
  role TEXT NOT NULL CHECK(role IN ('owner','staff','student')),
  status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','removed','blocked')),
  created_at DOUBLE PRECISION NOT NULL, updated_at DOUBLE PRECISION NOT NULL, UNIQUE(course_id, user_id));
CREATE TABLE IF NOT EXISTS staff_codes(
  id {PK}, course_id INTEGER NOT NULL REFERENCES courses(id), code_hash TEXT NOT NULL UNIQUE, last4 TEXT NOT NULL,
  created_by INTEGER NOT NULL REFERENCES users(id), created_at DOUBLE PRECISION NOT NULL,
  expires_at DOUBLE PRECISION NOT NULL, used_by INTEGER REFERENCES users(id), used_at DOUBLE PRECISION,
  revoked_at DOUBLE PRECISION);
CREATE TABLE IF NOT EXISTS documents(
  id TEXT PRIMARY KEY, title TEXT NOT NULL, kind TEXT NOT NULL, file_name TEXT NOT NULL,
  file_hash TEXT NOT NULL, tutor_only INTEGER NOT NULL DEFAULT 0, linked_doc_id TEXT, license TEXT);
CREATE TABLE IF NOT EXISTS solution_links(
  solution_id TEXT NOT NULL, pset_id TEXT NOT NULL, PRIMARY KEY(solution_id, pset_id));
CREATE TABLE IF NOT EXISTS chunks(
  id {PK}, doc_id TEXT NOT NULL REFERENCES documents(id), page INTEGER NOT NULL,
  text TEXT NOT NULL, tutor_only INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS guidelines(
  id {PK}, course_id INTEGER NOT NULL REFERENCES courses(id), text TEXT NOT NULL,
  doc_ids TEXT NOT NULL DEFAULT '[]', created_at DOUBLE PRECISION NOT NULL, updated_at DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS pauses(
  id {PK}, course_id INTEGER NOT NULL REFERENCES courses(id), starts_at DOUBLE PRECISION NOT NULL,
  ends_at DOUBLE PRECISION NOT NULL, message TEXT NOT NULL DEFAULT '', created_at DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS chats(
  id {PK}, course_id INTEGER NOT NULL REFERENCES courses(id), user_id INTEGER NOT NULL REFERENCES users(id),
  title TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'chat' CHECK(kind IN ('chat','pset','review','quiz')),
  doc_id TEXT, is_preview INTEGER NOT NULL DEFAULT 0,
  created_at DOUBLE PRECISION NOT NULL, updated_at DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS messages(
  id {PK}, chat_id INTEGER NOT NULL REFERENCES chats(id),
  role TEXT NOT NULL CHECK(role IN ('user','assistant')), content TEXT NOT NULL,
  citations TEXT NOT NULL DEFAULT '[]', memory_used TEXT NOT NULL DEFAULT '[]',
  course_id INTEGER, user_id INTEGER, is_preview INTEGER NOT NULL DEFAULT 0, doc_ids TEXT NOT NULL DEFAULT '[]',
  problem_doc_id TEXT, attempt_status TEXT, not_covered INTEGER NOT NULL DEFAULT 0,
  leak_blocked INTEGER NOT NULL DEFAULT 0, created_at DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS illustrations(
  id {PK}, chat_id INTEGER NOT NULL REFERENCES chats(id), message_id INTEGER REFERENCES messages(id),
  course_id INTEGER NOT NULL REFERENCES courses(id), user_id INTEGER NOT NULL REFERENCES users(id),
  concept TEXT NOT NULL, skill TEXT NOT NULL, modality TEXT NOT NULL, title TEXT NOT NULL,
  rationale TEXT NOT NULL DEFAULT '', spec_json TEXT NOT NULL DEFAULT '{}',
  artifact_html TEXT NOT NULL, manim_code TEXT NOT NULL DEFAULT '', created_at DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS memories(
  id {PK}, course_id INTEGER NOT NULL, user_id INTEGER NOT NULL REFERENCES users(id), text TEXT NOT NULL,
  created_at DOUBLE PRECISION NOT NULL, updated_at DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS usage_log(
  id {PK}, ts DOUBLE PRECISION NOT NULL, purpose TEXT NOT NULL, model TEXT NOT NULL,
  prompt_tokens INTEGER, completion_tokens INTEGER, cost DOUBLE PRECISION);
CREATE TABLE IF NOT EXISTS stripe_events(
  id TEXT PRIMARY KEY, type TEXT NOT NULL, created_at DOUBLE PRECISION NOT NULL)
"""

# Columns added to tables that v0 databases already have (added in place, idempotently).
ADDED_COLUMNS = {
    "users": {"account_type": "TEXT NOT NULL DEFAULT 'instructor'"},
    "documents": {
        "course_id": "INTEGER", "status": "TEXT NOT NULL DEFAULT 'ready'", "status_detail": "TEXT",
        "storage_path": "TEXT", "content_type": "TEXT", "pages": "INTEGER", "size_bytes": "INTEGER",
        "warning": "TEXT", "rights_confirmed": "INTEGER NOT NULL DEFAULT 0",
        "mode": "TEXT NOT NULL DEFAULT 'graded'", "release_at": "DOUBLE PRECISION",
        "confirm_answers": "INTEGER NOT NULL DEFAULT 0", "uploaded_by": "INTEGER",
        "created_at": "DOUBLE PRECISION", "updated_at": "DOUBLE PRECISION",
    },
    "usage_log": {"course_id": "INTEGER", "user_id": "INTEGER", "chat_id": "INTEGER", "total_tokens": "INTEGER"},
}

INDEXES = """
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS ix_users_email ON users(email);
CREATE INDEX IF NOT EXISTS ix_memberships_user ON memberships(user_id);
CREATE INDEX IF NOT EXISTS ix_documents_course ON documents(course_id);
CREATE INDEX IF NOT EXISTS ix_links_pset ON solution_links(pset_id);
CREATE INDEX IF NOT EXISTS ix_chats_course_user ON chats(course_id, user_id);
CREATE INDEX IF NOT EXISTS ix_messages_chat ON messages(chat_id);
CREATE INDEX IF NOT EXISTS ix_messages_course ON messages(course_id, created_at);
CREATE INDEX IF NOT EXISTS ix_messages_created ON messages(created_at);
CREATE INDEX IF NOT EXISTS ix_illustrations_chat ON illustrations(chat_id, id);
CREATE INDEX IF NOT EXISTS ix_memories_course_user ON memories(course_id, user_id);
CREATE INDEX IF NOT EXISTS ix_usage_course_user ON usage_log(course_id, user_id, ts);
CREATE INDEX IF NOT EXISTS ix_usage_ts ON usage_log(ts)
"""

IS_PG = bool(config.DATABASE_URL)
_pool = None


class _Conn:
    """Thin wrapper so call sites use `?` placeholders on both backends."""

    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql: str, params=()):
        if IS_PG:  # psycopg uses %s placeholders, so a literal % (as in LIKE 'local:%') must be doubled
            return self.raw.execute(sql.replace("%", "%%").replace("?", "%s"), params)
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
    raw = sqlite3.connect(config.DB_PATH, check_same_thread=False, timeout=30)
    raw.row_factory = sqlite3.Row
    raw.execute("PRAGMA foreign_keys=ON")
    try:
        yield _Conn(raw)
        raw.commit()
    finally:
        raw.close()


def _statements(sql: str) -> list[str]:
    return [s.strip() for s in sql.split(";") if s.strip()]


def table_exists(conn, table: str) -> bool:
    if IS_PG:
        return conn.execute("SELECT to_regclass(?) AS t", (table,)).fetchone()["t"] is not None
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def columns(conn, table: str) -> set[str]:
    if IS_PG:
        rows = conn.execute("SELECT column_name::text AS column_name FROM information_schema.columns "
                            "WHERE table_schema=current_schema() AND table_name=?", (table,)).fetchall()
        return {r["column_name"] for r in rows}
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _archive_v0(conn) -> None:
    """v0 had demo identities (name + role) and course-less chats. Copy those tables to v0_* and drop them,
    so v1 can create them in its own shape. Course materials (documents, chunks) and usage_log are kept."""
    for t in V0_CONVERSATION_TABLES:
        if table_exists(conn, t) and not table_exists(conn, f"v0_{t}"):
            conn.execute(f"CREATE TABLE v0_{t} AS SELECT * FROM {t}")
    for t in ["messages", "memories", "chats", "users"]:  # children first
        if table_exists(conn, t):
            conn.execute(f"DROP TABLE {t}")


def init_db() -> None:
    pk = "BIGSERIAL PRIMARY KEY" if IS_PG else "INTEGER PRIMARY KEY"
    with db() as conn:
        if not IS_PG:
            conn.execute("PRAGMA journal_mode=WAL")  # background jobs write while requests read
        if table_exists(conn, "users") and "role" in columns(conn, "users"):
            _archive_v0(conn)
        for st in _statements(SCHEMA.replace("{PK}", pk)):
            conn.execute(st)
        for table, cols in ADDED_COLUMNS.items():
            have = columns(conn, table)
            for name, ddl in cols.items():
                if name not in have:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
        conn.execute("UPDATE documents SET kind='solution' WHERE kind='problem_set_solution'")
        conn.execute("INSERT INTO solution_links(solution_id,pset_id) SELECT id, linked_doc_id FROM documents "
                     "WHERE linked_doc_id IS NOT NULL ON CONFLICT DO NOTHING")  # v0 kept one link per solution
        # Migrate existing users: any user who has student memberships and no owner/staff memberships is a student.
        conn.execute(
            "UPDATE users SET account_type='student' WHERE id IN ("
            "  SELECT user_id FROM memberships WHERE role='student' AND status='active'"
            ") AND id NOT IN ("
            "  SELECT user_id FROM memberships WHERE role IN ('owner','staff') AND status='active'"
            ")"
        )
        for st in _statements(INDEXES):
            conn.execute(st)
        if IS_PG:
            # Supabase exposes the public schema through its REST API. Enabling RLS with no policies
            # denies the anon/authenticated roles everything; this backend connects as a bypass role.
            for t in TABLES + [f"v0_{t}" for t in V0_CONVERSATION_TABLES]:
                if table_exists(conn, t):
                    conn.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")


def lock_row(conn, table: str, row_id) -> None:
    """Serialise writers on one row until this transaction commits (seat caps): count-then-insert is safe after this.
    Postgres locks the row; SQLite takes the database write lock, which must happen before any read it depends on."""
    if IS_PG:
        conn.execute(f"SELECT 1 FROM {table} WHERE id=? FOR UPDATE", (row_id,))
    elif not conn.raw.in_transaction:
        conn.execute("BEGIN IMMEDIATE")


def now() -> float:
    return time.time()
