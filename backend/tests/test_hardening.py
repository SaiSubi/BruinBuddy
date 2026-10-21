"""Regression tests for the v1 review findings: mode selection, solution release, races, payments, redirects."""
import hashlib
import hmac
import json
import threading
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import billing, config, llm, materials
from app.materials import file_url
from app.tutor import SAFE_REPLY
from conftest import (NOTES, PSET2, SOL1, SOL2, ask, create_course, execute, join, new_chat, new_user, q1, setup_course,
                      student_in, upload_ok)

PSET2_PROBLEM = PSET2.split("Problem 1. ")[1]  # long enough to be detected as a pasted Problem Set 2 problem


def _student_view(s, cid):
    return {m["id"] for m in s.get(f"/api/courses/{cid}/materials").json()["materials"]}


# ---- 1. the strictest matching mode applies ----------------------------------------------------
def test_naming_a_laxer_set_cant_unlock_a_pasted_graded_problem(app):
    owner = new_user(app)
    c = setup_course(owner)
    owner.patch(f"/api/courses/{c['id']}/materials/{c['p1']}", json={"mode": "practice"})
    s = student_in(app, c)
    done = ask(s, new_chat(s, c["id"]), f"pset 1 question: {PSET2_PROBLEM}")[-1]["message"]
    assert done["rule"]["doc_id"] == c["p2"] and done["rule"]["mode"] == "graded"
    attached = ask(s, new_chat(s, c["id"], "pset", c["p1"]), f"Explain this one fully: {PSET2_PROBLEM}")
    assert [e["type"] for e in attached] == ["delta", "done"]  # buffered like any Graded turn
    assert attached[-1]["message"]["rule"]["doc_id"] == c["p2"]
    owner.patch(f"/api/courses/{c['id']}/materials/{c['p1']}", json={"mode": "open"})
    done = ask(s, new_chat(s, c["id"]), f"pset 1: {PSET2_PROBLEM}")[-1]["message"]
    assert done["rule"]["mode"] == "graded"


def test_practice_checker_never_sees_a_solution_that_covers_a_graded_set(app):
    owner = new_user(app)
    c = setup_course(owner)
    combined = "Combined Solutions. The magic constant for both sets is forty two exactly as shown in the key."
    upload_ok(owner, c["id"], "solution", {"Combined Solutions.txt": combined}, [c["p1"], c["p2"]])
    owner.patch(f"/api/courses/{c['id']}/materials/{c['p1']}", json={"mode": "practice"})
    s = student_in(app, c)
    ask(s, new_chat(s, c["id"], "pset", c["p1"]), "I tried problem 1 and got 3/8, magic constant forty two?")
    sent = [x for x in llm.MOCK_CALLS if x["purpose"] == "checker"][-1]["messages"][1]["content"]
    excerpts = sent.split("RECENT CONVERSATION")[0]
    assert "favorable sequences" in excerpts and "magic constant" not in excerpts


# ---- 2. removing one linked set never releases a multi-set solution ---------------------------
@pytest.mark.parametrize("removal", ["delete", "recategorise"])
def test_removing_a_linked_set_keeps_the_solution_protected(app, removal):
    owner = new_user(app)
    c = setup_course(owner)
    shared = upload_ok(owner, c["id"], "solution", {"Shared Solutions.txt": SOL1 + "\n\n" + SOL2}, [c["p1"], c["p2"]])[0]
    owner.patch(f"/api/courses/{c['id']}/materials/{c['p2']}", json={"mode": "open"})
    s = student_in(app, c)
    assert shared not in _student_view(s, c["id"])  # P1 is still Graded
    if removal == "delete":
        assert owner.delete(f"/api/courses/{c['id']}/materials/{c['p1']}").status_code == 200
    else:
        assert owner.patch(f"/api/courses/{c['id']}/materials/{c['p1']}", json={"kind": "reading"}).status_code == 200
    assert shared not in _student_view(s, c["id"])
    assert TestClient(app).get(file_url(shared)).status_code == 404
    staff_row = next(m for m in owner.get(f"/api/courses/{c['id']}/materials").json()["materials"] if m["id"] == shared)
    assert staff_row["psets"] == [] and "Link it again" in staff_row["warning"]


# ---- 3. seat caps hold under concurrent joins ---------------------------------------------------
def test_concurrent_joins_cannot_exceed_the_seat_cap(app):
    owner = new_user(app)
    cid = create_course(owner, student_seats=1)
    code = owner.get(f"/api/courses/{cid}").json()["student_code"]
    students = [new_user(app) for _ in range(5)]
    barrier, results = threading.Barrier(len(students)), []

    def go(client):
        barrier.wait()
        results.append(client.post("/api/join", json={"code": code}).status_code)

    threads = [threading.Thread(target=go, args=(s,)) for s in students]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == [200, 409, 409, 409, 409]
    assert q1("SELECT COUNT(*) AS n FROM memberships WHERE course_id=? AND role='student' AND status='active'",
              cid)["n"] == 1


# ---- 4. deleting a tagged material doesn't break guideline saving --------------------------------
def test_guidelines_survive_deleting_a_tagged_material(app):
    owner = new_user(app)
    c = setup_course(owner)
    url = f"/api/courses/{c['id']}/guidelines"
    owner.put(url, json={"general": "", "tagged": [{"text": "Use tree diagrams.", "doc_ids": [c["notes"], c["reading"]]}]})
    owner.delete(f"/api/courses/{c['id']}/materials/{c['reading']}")
    assert owner.get(url).json()["tagged"][0]["doc_ids"] == [c["notes"]]
    stale = {"general": "", "tagged": [{"text": "Use tree diagrams.", "doc_ids": [c["notes"], c["reading"]]}]}
    assert owner.put(url, json=stale).status_code == 200  # a stale id is dropped, not an error
    only_deleted = {"general": "", "tagged": [{"text": "x", "doc_ids": [c["reading"]]}]}
    assert owner.put(url, json=only_deleted).status_code == 422


# ---- 5–7. payments --------------------------------------------------------------------------------
def test_webhook_failure_lets_stripe_retry(app, monkeypatch):
    owner = new_user(app)
    cid = create_course(owner, activate=False)
    price = q1("SELECT price_cents FROM courses WHERE id=?", cid)["price_cents"]
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test_dummy")
    monkeypatch.setattr(config, "STRIPE_WEBHOOK_SECRET", "whsec_dummy")
    event = {"id": f"evt_retry_{cid}", "type": "checkout.session.completed", "data": {"object": {
        "id": "cs_x", "payment_status": "paid", "currency": "usd", "amount_total": price,
        "metadata": {"course_id": str(cid)}}}}
    payload = json.dumps(event)

    def send(client):
        t = int(time.time())
        sig = hmac.new(b"whsec_dummy", f"{t}.{payload}".encode(), hashlib.sha256).hexdigest()
        return client.post("/api/stripe/webhook", content=payload, headers={"stripe-signature": f"t={t},v1={sig}"})

    real = billing._activate
    monkeypatch.setattr(billing, "_activate", lambda *a: (_ for _ in ()).throw(RuntimeError("db blip")))
    assert send(TestClient(app, raise_server_exceptions=False)).status_code == 500
    monkeypatch.setattr(billing, "_activate", real)
    assert send(TestClient(app)).json() == {"received": True}  # not swallowed as a duplicate
    assert q1("SELECT status FROM courses WHERE id=?", cid)["status"] == "active"


def test_confirm_rejects_an_underpaid_session(app, monkeypatch):
    owner = new_user(app)
    cid = create_course(owner, activate=False)
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test_dummy")
    session = {"id": "cs_low", "payment_status": "paid", "currency": "usd", "amount_total": 50,
               "metadata": {"course_id": str(cid)}}
    monkeypatch.setattr(billing, "_stripe", lambda: SimpleNamespace(v1=SimpleNamespace(checkout=SimpleNamespace(
        sessions=SimpleNamespace(retrieve=lambda sid: SimpleNamespace(to_dict=lambda: session))))))
    assert owner.post(f"/api/courses/{cid}/checkout/confirm", json={"session_id": "cs_low"}).json()["status"] == "pending"


@pytest.mark.parametrize("raw, expected", [
    ("http://localhost:5173", "http://localhost:5173"),
    ("http://127.0.0.1:8000/", "http://127.0.0.1:8000"),
    ("http://localhost:@evil.example", None),
    ("http://localhost:5173@evil.example", None),
    ("https://evil.example", None),
    ("http://localhost:5173/path?x=1", None),
    ("javascript:alert(1)", None),
])
def test_return_urls_are_parsed(raw, expected):
    assert billing._return_base(raw) == (expected or config.APP_URL)


# ---- 8. release dates ----------------------------------------------------------------------------
def test_release_date_must_be_a_real_date(app):
    owner = new_user(app)
    c = setup_course(owner)
    url = f"/api/courses/{c['id']}/materials/{c['p1']}"
    assert owner.patch(url, json={"release_at": 0}).status_code == 422
    assert owner.patch(url, json={"release_at": time.time() + 3600}).status_code == 200


# ---- 9. staff can be blocked ----------------------------------------------------------------------
def test_owner_can_block_staff_and_they_cannot_rejoin(app):
    owner = new_user(app)
    cid = create_course(owner, staff_seats=3)
    code = owner.get(f"/api/courses/{cid}").json()["student_code"]
    ta, other_ta = new_user(app, "TA"), new_user(app, "TA 2")
    join(ta, owner.post(f"/api/courses/{cid}/staff-codes").json()["code"])
    join(other_ta, owner.post(f"/api/courses/{cid}/staff-codes").json()["code"])
    assert other_ta.post(f"/api/courses/{cid}/members/{ta.user['id']}", json={"action": "block"}).status_code == 403
    assert owner.post(f"/api/courses/{cid}/members/{ta.user['id']}", json={"action": "remove"}).status_code == 200
    assert owner.post(f"/api/courses/{cid}/members/{ta.user['id']}", json={"action": "block"}).status_code == 200
    assert ta.post("/api/join", json={"code": code}).status_code == 403
    assert ta.post("/api/join", json={"code": owner.post(f"/api/courses/{cid}/staff-codes").json()["code"]}).status_code == 403
    staff = {p["user_id"]: p["status"] for p in owner.get(f"/api/courses/{cid}/members").json()["staff"]}
    assert staff[ta.user["id"]] == "blocked"


# ---- 10. a stale processing job can't overwrite a newer file --------------------------------------
def test_stale_processing_job_is_discarded(app):
    owner = new_user(app)
    cid = create_course(owner)
    doc = upload_ok(owner, cid, "lecture_notes", {"notes.txt": NOTES})[0]
    newer = NOTES.replace("Bayes", "Markov") + "\nMarkov chains have memoryless transitions between states."
    owner.post(f"/api/courses/{cid}/materials/{doc}/file", files={"file": ("notes.txt", newer.encode())})
    materials.process_document(doc, NOTES.encode())  # the original upload's job finishing late
    from app.db import db
    with db() as conn:
        text = " ".join(r["text"] for r in conn.execute("SELECT text FROM chunks WHERE doc_id=?", (doc,)).fetchall())
    assert "Markov chains" in text
    execute("UPDATE documents SET status='processing' WHERE id=?", doc)
    assert owner.post(f"/api/courses/{cid}/materials/{doc}/retry").status_code == 409


# ---- 11. the model leak check fails closed --------------------------------------------------------
def test_unreadable_leak_check_counts_as_a_leak(app, monkeypatch):
    owner = new_user(app)
    c = setup_course(owner)
    s = student_in(app, c)
    real = llm._mock_complete
    monkeypatch.setattr(llm, "_mock_complete", lambda purpose, messages, attr: (
        '{"leaks": fal' if purpose == "guard" else real(purpose, messages, attr)))
    done = ask(s, new_chat(s, c["id"], "pset", c["p1"]), "How do I start?")[-1]["message"]
    assert done["content"] == SAFE_REPLY


def test_leak_verdict_is_read_leniently_and_retried(app, monkeypatch):
    owner = new_user(app)
    c = setup_course(owner)
    s = student_in(app, c)
    real = llm._mock_complete
    answers = iter(['Comparing the reply with $\\frac{3}{8}$ in the excerpts... the reply only hints. {"leaks": false}'])
    monkeypatch.setattr(llm, "_mock_complete", lambda purpose, messages, attr: (
        next(answers, '{"leaks": false}') if purpose == "guard" else real(purpose, messages, attr)))
    done = ask(s, new_chat(s, c["id"], "pset", c["p1"]), "How do I start?")[-1]["message"]
    assert done["content"] != SAFE_REPLY  # the verdict after an explanation (with braces) is still read
    calls = []
    monkeypatch.setattr(llm, "_mock_complete", lambda purpose, messages, attr: (
        calls.append(1) or ('Let me think about this carefully' if len(calls) == 1 else '{"leaks": false}')
        if purpose == "guard" else real(purpose, messages, attr)))
    done = ask(s, new_chat(s, c["id"], "pset", c["p1"]), "How do I start?")[-1]["message"]
    assert done["content"] != SAFE_REPLY and len(calls) == 2  # no verdict -> asked again once


@pytest.mark.parametrize("kind", ["chat", "pset"])
def test_an_empty_model_reply_is_an_error_not_a_blank_answer(app, monkeypatch, kind):
    owner = new_user(app)
    c = setup_course(owner)
    s = student_in(app, c)
    monkeypatch.setattr(llm, "mock_tutor_text", lambda system: "")
    chat = new_chat(s, c["id"], kind, c["p1"] if kind == "pset" else None)
    events = ask(s, chat, "Explain conditional probability")
    assert events[-1] == {"type": "error", "message": "The tutor didn't return an answer. Please try again."}
    assert [m["role"] for m in s.get(f"/api/chats/{chat}").json()["messages"]] == ["user"]  # the question is kept
