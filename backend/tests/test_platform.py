"""Migration from v0, production safety checks, CORS and file storage."""
import sqlite3

import httpx
import pytest
from fastapi.testclient import TestClient

from app import config, db as dbmod, storage
from app.materials import file_url
from conftest import new_user, setup_course

V0_SCHEMA = """
CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL, created_at DOUBLE PRECISION NOT NULL,
  UNIQUE(name, role));
CREATE TABLE chats(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), title TEXT NOT NULL,
  created_at DOUBLE PRECISION NOT NULL, updated_at DOUBLE PRECISION NOT NULL);
CREATE TABLE messages(id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL REFERENCES chats(id), role TEXT NOT NULL,
  content TEXT NOT NULL, citations TEXT NOT NULL DEFAULT '[]', memory_used TEXT NOT NULL DEFAULT '[]',
  created_at DOUBLE PRECISION NOT NULL);
CREATE TABLE memories(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), text TEXT NOT NULL,
  created_at DOUBLE PRECISION NOT NULL, updated_at DOUBLE PRECISION NOT NULL);
CREATE TABLE documents(id TEXT PRIMARY KEY, title TEXT NOT NULL, kind TEXT NOT NULL, file_name TEXT NOT NULL,
  file_hash TEXT NOT NULL, tutor_only INTEGER NOT NULL DEFAULT 0, linked_doc_id TEXT, license TEXT);
CREATE TABLE chunks(id INTEGER PRIMARY KEY, doc_id TEXT NOT NULL REFERENCES documents(id), page INTEGER NOT NULL,
  text TEXT NOT NULL, tutor_only INTEGER NOT NULL DEFAULT 0);
CREATE TABLE usage_log(id INTEGER PRIMARY KEY, ts DOUBLE PRECISION NOT NULL, purpose TEXT NOT NULL, model TEXT NOT NULL,
  prompt_tokens INTEGER, completion_tokens INTEGER, cost DOUBLE PRECISION);
INSERT INTO users VALUES(1, 'Alex', 'student', 1);
INSERT INTO chats VALUES(1, 1, 'old chat', 1, 1);
INSERT INTO messages(chat_id, role, content, created_at) VALUES(1, 'user', 'hello from v0', 1);
INSERT INTO documents VALUES('d1', 'Problem Set 01 Solutions', 'problem_set_solution', 'pset01_sol.pdf', 'h', 1, 'd0', '');
INSERT INTO usage_log(ts, purpose, model, prompt_tokens, completion_tokens, cost) VALUES(1, 'tutor', 'm', 10, 5, 0.1);
"""


@pytest.mark.skipif(dbmod.IS_PG, reason="builds a SQLite file")
def test_v0_database_is_migrated_in_place(tmp_path, monkeypatch):
    path = tmp_path / "v0.db"
    con = sqlite3.connect(path)
    con.executescript(V0_SCHEMA)
    con.close()
    monkeypatch.setattr(config, "DB_PATH", path)
    dbmod.init_db()
    dbmod.init_db()  # idempotent
    con = sqlite3.connect(path)
    assert con.execute("SELECT content FROM v0_messages").fetchone() == ("hello from v0",)
    assert con.execute("SELECT name, role FROM v0_users").fetchone() == ("Alex", "student")
    cols = {r[1] for r in con.execute("PRAGMA table_info(users)")}
    assert {"auth_id", "email"} <= cols and "role" not in cols
    assert con.execute("SELECT COUNT(*) FROM users").fetchone() == (0,)
    assert con.execute("SELECT kind, status, mode, course_id FROM documents").fetchone() == ("solution", "ready", "graded", None)
    assert con.execute("SELECT solution_id, pset_id FROM solution_links").fetchall() == [("d1", "d0")]
    assert con.execute("SELECT total_tokens, prompt_tokens FROM usage_log").fetchone() == (None, 10)
    assert {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")} >= {
        "courses", "memberships", "staff_codes", "solution_links", "guidelines", "pauses", "stripe_events"}


@pytest.mark.parametrize("change, problem", [
    ({"AUTH_PROVIDER": "local"}, "AUTH_PROVIDER"),
    ({"STRIPE_SECRET_KEY": ""}, "STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET"),
    ({"STRIPE_SECRET_KEY": "sk_live_123"}, "test-mode key"),
    ({"MOCK_LLM": True}, "BB_MOCK_LLM"),
    ({"SECRET_KEY": "short"}, "SECRET_KEY"),
])
def test_production_refuses_unsafe_config(monkeypatch, change, problem):
    good = {"PRODUCTION": True, "SECRET_KEY": "s" * 40, "DATABASE_URL": "postgresql://x", "MOCK_LLM": False,
            "OPENROUTER_API_KEY": "k", "SUPABASE_URL": "https://p.supabase.co", "SUPABASE_SERVICE_KEY": "svc",
            "SUPABASE_ANON_KEY": "anon", "AUTH_PROVIDER": "supabase", "STRIPE_SECRET_KEY": "sk_test_1",
            "STRIPE_WEBHOOK_SECRET": "whsec_1"}
    for k, v in good.items():
        monkeypatch.setattr(config, k, v)
    config.check_production_settings()  # the good configuration boots
    for k, v in change.items():
        monkeypatch.setattr(config, k, v)
    with pytest.raises(RuntimeError, match=problem):
        config.check_production_settings()


def test_cors_only_for_allowed_origin(app):
    c = TestClient(app)
    ok = c.options("/api/me", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "PATCH"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = c.options("/api/me", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in bad.headers


def test_file_links_are_scoped_and_bound(app):
    owner = new_user(app)
    c = setup_course(owner)
    anon = TestClient(app)
    assert anon.get(f"/files/{c['notes']}").status_code == 403
    assert anon.get(f"/files/{c['notes']}?t=123.p.abc").status_code == 403
    other = file_url(c["reading"]).split("?t=")[1]
    assert anon.get(f"/files/{c['notes']}?t={other}").status_code == 403  # a token is bound to one document
    assert anon.get(file_url(c["notes"])).status_code == 200


def test_files_redirect_to_signed_storage_url(app, monkeypatch):
    owner = new_user(app)
    c = setup_course(owner)
    monkeypatch.setattr(storage, "configured", lambda: True)
    monkeypatch.setattr(storage, "signed_url", lambda name: f"https://example.test/signed/{name}?token=x")
    r = TestClient(app).get(file_url(c["notes"]), follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"].startswith("https://example.test/signed/courses/")
    assert r.headers["cache-control"] == "no-store"
    assert TestClient(app).get(file_url(c["s1"]), follow_redirects=False).status_code == 404  # never for a solution

    def missing(name):
        raise storage.NotFound(name)
    monkeypatch.setattr(storage, "signed_url", missing)
    assert TestClient(app).get(file_url(c["notes"]), follow_redirects=False).status_code == 404

    def down(name):
        raise httpx.ConnectError("down")
    monkeypatch.setattr(storage, "signed_url", down)
    assert TestClient(app).get(file_url(c["notes"]), follow_redirects=False).status_code == 502


def test_health_and_config(app):
    h = TestClient(app).get("/api/health").json()
    assert h == {"ok": True, "llm": "mock", "auth": "local", "billing": "mock"}
    cfg = TestClient(app).get("/api/config").json()
    assert cfg["auth"]["provider"] == "local" and cfg["auth"]["supabase_anon_key"] == ""
    assert cfg["upload"]["types"] == [".pdf", ".txt", ".md"]
