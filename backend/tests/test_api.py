"""API tests using the mock LLM (no key, no cost).  Run: BB_MOCK_LLM=1 pytest backend/tests"""
import json
import os

os.environ["BB_MOCK_LLM"] = "1"

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def q1(sql, *params):
    from app.db import db
    with db() as conn:
        return conn.execute(sql, params).fetchone()


def sign_in(client, name, role="student", code=""):
    r = client.post("/api/session", json={"name": name, "role": role, "code": code})
    assert r.status_code == 200, r.text
    client.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return r.json()


def new_client(name, role="student"):
    c = TestClient(app)
    sign_in(c, name, role)
    return c


def ask(client, chat_id, text):
    r = client.post(f"/api/chats/{chat_id}/messages", json={"content": text})
    events = [json.loads(l[6:]) for l in r.text.splitlines() if l.startswith("data: ")]
    return events


def test_requires_sign_in(client):
    c = TestClient(app)
    assert c.get("/api/chats").status_code == 401


def test_chat_with_citations_and_persistence(client):
    sign_in(client, "Alex")
    chat = client.post("/api/chats").json()
    events = ask(client, chat["id"], "What is the central limit theorem?")
    done = events[-1]
    assert done["type"] == "done"
    assert done["message"]["citations"], "expected at least one citation"
    c = done["message"]["citations"][0]
    assert c["url"].startswith("/files/")
    assert "?t=" in c["url"]
    assert TestClient(app).get(c["url"].split("#")[0]).status_code == 200  # signed link works without a header
    reopened = client.get(f"/api/chats/{chat['id']}").json()
    assert [m["role"] for m in reopened["messages"]] == ["user", "assistant"]
    assert reopened["title"].startswith("What is the central")


def test_multiple_chats_and_isolation(client):
    sign_in(client, "Alex")
    a = client.post("/api/chats").json()
    b = client.post("/api/chats").json()
    assert len(client.get("/api/chats").json()) >= 2
    other = new_client("Bea")
    assert other.get(f"/api/chats/{a['id']}").status_code == 404
    assert other.post(f"/api/chats/{b['id']}/messages", json={"content": "hi"}).status_code == 404


def test_memory_created_and_used(client):
    sign_in(client, "Memo")
    c1 = client.post("/api/chats").json()
    ask(client, c1["id"], "Help me review covariance")
    import time; time.sleep(0.5)  # memory update runs in a background thread
    c2 = client.post("/api/chats").json()
    done = ask(client, c2["id"], "What should I study next?")[-1]
    assert done["message"]["memory_used"], "expected memory from chat 1 to be used in chat 2"


def test_dashboard_counts_questions_and_is_professor_only(client):
    prof = new_client("Prof", "professor")
    before = prof.get("/api/dashboard").json()["questions_asked"]
    sign_in(client, "Counter")
    chat = client.post("/api/chats").json()
    ask(client, chat["id"], "one")
    ask(client, chat["id"], "two")
    assert prof.get("/api/dashboard").json()["questions_asked"] == before + 2
    assert client.get("/api/dashboard").status_code == 403
    assert prof.get("/api/chats").status_code == 403


def test_solution_files_are_never_served(client):
    sign_in(client, "Alex")
    sol = q1("SELECT id FROM documents WHERE tutor_only=1 LIMIT 1")["id"]
    from app import auth
    assert client.get(f"/files/{sol}?t={auth.make_file_token(sol)}").status_code == 404  # even with a valid token
    sol_chunk = q1("SELECT id FROM chunks WHERE tutor_only=1 LIMIT 1")["id"]
    assert client.get(f"/api/sources/{sol_chunk}").status_code == 404


def test_no_tutor_only_chunk_is_retrievable(client):
    from app.main import state
    assert all(not c.file_name.endswith("_sol.pdf") for c in state["index"].chunks)


def test_assigned_problem_detected_and_leak_guard():
    from app.main import state
    idx, guard = state["index"], state["guard"]
    assert idx.problem_doc_from_reference("can you solve pset 4 problem 2?")
    sol_text = q1("SELECT text FROM chunks WHERE tutor_only=1 AND length(text)>800 LIMIT 1")["text"]
    assert guard.leaks(sol_text), "verbatim solution text must be flagged"
    assert not guard.leaks("Think about what the definition of conditional probability says. What is given?")


def _pset_problem_text():
    return q1("SELECT c.text FROM chunks c JOIN documents d ON d.id=c.doc_id "
              "WHERE d.file_name='mit18_05_s22_pset04.pdf' AND length(c.text)>500 LIMIT 1")["text"]


def test_pasted_assigned_problem_is_detected_and_gets_a_hint(client):
    from app.main import state
    text = _pset_problem_text()
    assert state["index"].match_problem(text[:600])[1] >= 0.6
    sign_in(client, "Alex")
    chat = client.post("/api/chats").json()
    done = ask(client, chat["id"], "Can you give me the answer to this?\n" + text[:600])[-1]
    assert done["type"] == "done"
    assert "won't give the answer" in done["message"]["content"]  # mock tutor's assigned-problem branch


def test_leaked_solution_text_is_replaced_before_reaching_the_student(client, monkeypatch):
    from app import llm
    from app.tutor import SAFE_REPLY
    sol_text = q1("SELECT text FROM chunks WHERE tutor_only=1 AND length(text)>800 LIMIT 1")["text"]
    monkeypatch.setattr(llm, "_mock_stream", lambda messages: iter([sol_text]))
    sign_in(client, "Alex")
    chat = client.post("/api/chats").json()
    events = ask(client, chat["id"], "Explain the central limit theorem")  # non-assigned path: stream then guard
    assert events[-1]["message"]["content"] == SAFE_REPLY
    assert any(e["type"] == "replace" for e in events)
    stored = client.get(f"/api/chats/{chat['id']}").json()["messages"][-1]["content"]
    assert stored == SAFE_REPLY


# ---- production hardening -----------------------------------------------------------
def test_forged_and_tampered_tokens_are_rejected():
    c = TestClient(app)
    assert c.get("/api/chats", headers={"Authorization": "Bearer u.1.9999999999.deadbeef"}).status_code == 401
    assert c.get("/api/chats", headers={"Authorization": "Bearer 1"}).status_code == 401
    good = new_client("Tamper")
    token = good.headers["Authorization"].split(" ")[1]
    uid = token.split(".")[1]
    forged = token.replace(f"u.{uid}.", f"u.{int(uid) + 1}.", 1)
    assert c.get("/api/chats", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_expired_token_rejected(monkeypatch):
    from app import auth
    monkeypatch.setattr(config, "TOKEN_TTL_SECONDS", -10)
    c = TestClient(app)
    r = c.post("/api/session", json={"name": "Old", "role": "student"})
    assert c.get("/api/me", headers={"Authorization": f"Bearer {r.json()['token']}"}).status_code == 401


def test_access_codes(monkeypatch):
    monkeypatch.setattr(config, "STUDENT_CODE", "s3cret")
    monkeypatch.setattr(config, "PROFESSOR_CODE", "profcode")
    c = TestClient(app)
    assert c.get("/api/config").json()["student_code_required"] is True
    assert c.post("/api/session", json={"name": "A", "role": "student"}).status_code == 403
    assert c.post("/api/session", json={"name": "A", "role": "student", "code": "wrong"}).status_code == 403
    assert c.post("/api/session", json={"name": "A", "role": "student", "code": "s3cret"}).status_code == 200
    assert c.post("/api/session", json={"name": "P", "role": "professor", "code": "s3cret"}).status_code == 403
    assert c.post("/api/session", json={"name": "P", "role": "professor", "code": "profcode"}).status_code == 200


def test_professor_signin_disabled_in_production_without_code(monkeypatch):
    monkeypatch.setattr(config, "PRODUCTION", True)
    monkeypatch.setattr(config, "PROFESSOR_CODE", "")
    r = TestClient(app).post("/api/session", json={"name": "P", "role": "professor"})
    assert r.status_code == 403


def test_daily_limits(client, monkeypatch):
    sign_in(client, "Limited")
    chat = client.post("/api/chats").json()
    monkeypatch.setattr(config, "DAILY_MESSAGE_LIMIT", 2)
    assert ask(client, chat["id"], "one")[-1]["type"] == "done"
    assert ask(client, chat["id"], "two")[-1]["type"] == "done"
    r = client.post(f"/api/chats/{chat['id']}/messages", json={"content": "three"})
    assert r.status_code == 429
    monkeypatch.setattr(config, "DAILY_MESSAGE_LIMIT", 1000)
    monkeypatch.setattr(config, "GLOBAL_DAILY_LIMIT", 1)
    assert client.post(f"/api/chats/{chat['id']}/messages", json={"content": "four"}).status_code == 429


def test_file_links_require_valid_token(client):
    sign_in(client, "Alex")
    doc = q1("SELECT id FROM documents WHERE tutor_only=0 LIMIT 1")["id"]
    anon = TestClient(app)
    assert anon.get(f"/files/{doc}").status_code == 403
    assert anon.get(f"/files/{doc}?t=123.abc").status_code == 403
    from app import auth
    other_doc_token = auth.make_file_token("some-other-doc")
    assert anon.get(f"/files/{doc}?t={other_doc_token}").status_code == 403  # token is bound to one document


def test_cors_only_for_allowed_origin():
    c = TestClient(app)
    ok = c.options("/api/chats", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = c.options("/api/chats", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in bad.headers


def test_production_refuses_unsafe_config(monkeypatch):
    monkeypatch.setattr(config, "PRODUCTION", True)
    monkeypatch.setattr(config, "SECRET_KEY", "short")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        config.check_production_settings()
