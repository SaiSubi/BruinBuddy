"""The AI teaching assistant's Q&A: the knowledge base (extraction, review, FAQ), answering within the staff's rules,
escalation to the shared staff inbox, the learning loop, gates, solution protection, privacy and tenancy."""
import io
import json
import time
import zipfile

from conftest import SOL1, create_course, new_user, q1, setup_course, student_in

from app import llm

QA_DOC = """Course Q&A, Fall 2025

Q: Can we use R or Python for the simulations in the problem sets?
A: Either is fine. Submit your code with the write-up.

Q: Is the final exam cumulative?
A: Yes, the final covers the whole course, with extra weight on the last three weeks.

Q: Where do I find the course reader?
A: It is on the course website under Readings."""


def qna_calls(purpose=None):
    return [c for c in llm.MOCK_CALLS if c["purpose"].startswith("qna_") and (purpose is None or c["purpose"] == purpose)]


def upload_qa(owner, cid, files, rights=True):
    return owner.post(f"/api/courses/{cid}/qna/sources", data={"rights": "true" if rights else "false"},
                      files=[("files", (name, data if isinstance(data, bytes) else data.encode(), "application/octet-stream"))
                             for name, data in files.items()])


def approved_kb(app, **kw):
    owner = new_user(app, "Prof")
    cid = create_course(owner, **kw)
    assert upload_qa(owner, cid, {"past-qa.txt": QA_DOC}).status_code == 200
    assert owner.post(f"/api/courses/{cid}/qna/pairs/approve", json={}).json()["approved"] == 3
    code = owner.get(f"/api/courses/{cid}").json()["student_code"]
    return owner, cid, code


def ask(client, cid, question):
    r = client.post(f"/api/courses/{cid}/qna", json={"question": question})
    assert r.status_code == 200, r.text
    return r.json()


def docx(paragraphs: list[str]) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", f'<w:document xmlns:w="x"><w:body>{body}</w:body></w:document>')
    return buf.getvalue()


def test_upload_extracts_pending_pairs_for_review(app):
    owner = new_user(app, "Prof")
    cid = create_course(owner)
    code = owner.get(f"/api/courses/{cid}").json()["student_code"]
    assert upload_qa(owner, cid, {"qa.txt": QA_DOC}, rights=False).status_code == 422
    assert upload_qa(owner, cid, {"qa.exe": "x"}).status_code == 422
    r = upload_qa(owner, cid, {"qa.txt": QA_DOC, "faq.docx": docx(["Q: When are office hours?", "A: Tuesdays at 3 pm."])})
    assert r.status_code == 200, r.text
    kb = owner.get(f"/api/courses/{cid}/qna/knowledge").json()
    assert {s["file_name"]: (s["status"], s["pairs_found"]) for s in kb["sources"]} == {"qa.txt": ("ready", 3),
                                                                                       "faq.docx": ("ready", 1)}
    assert {p["status"] for p in kb["pairs"]} == {"pending"}
    usage = q1("SELECT COUNT(*) AS n FROM usage_log WHERE purpose='qna_extract' AND course_id=? AND user_id=?",
               cid, owner.user["id"])
    assert usage["n"] == 2

    student = student_in(app, {"code": code}, "Alice")
    assert student.get(f"/api/courses/{cid}/qna/knowledge").status_code == 403
    t = ask(student, cid, "Can we use Python for the simulations?")
    assert t["messages"][-1]["citations"] == []  # pending pairs are never used

    docx_source = next(s for s in kb["sources"] if s["file_name"] == "faq.docx")
    assert owner.post(f"/api/courses/{cid}/qna/pairs/approve", json={"source_id": docx_source["id"]}).json()["approved"] == 1
    pending = [p for p in owner.get(f"/api/courses/{cid}/qna/knowledge").json()["pairs"] if p["status"] == "pending"]
    assert len(pending) == 3
    p = pending[0]
    assert owner.patch(f"/api/courses/{cid}/qna/pairs/{p['id']}", json={"faq": True}).status_code == 422  # approve first
    r = owner.patch(f"/api/courses/{cid}/qna/pairs/{p['id']}", json={"answer": "Edited answer.", "status": "approved", "faq": True})
    assert r.json()["answer"] == "Edited answer." and r.json()["faq"] is True
    qa_source = next(s for s in kb["sources"] if s["file_name"] == "qa.txt")
    owner.delete(f"/api/courses/{cid}/qna/sources/{qa_source['id']}")
    left = owner.get(f"/api/courses/{cid}/qna/knowledge").json()["pairs"]
    assert len(left) == 2 and all(x["status"] == "approved" for x in left)  # pending ones went with the document


def test_ai_answers_from_past_qa_and_staff_only_see_counts(app):
    owner, cid, code = approved_kb(app)
    student = student_in(app, {"code": code}, "Alice")
    t = ask(student, cid, "Can we use R or Python for the simulations in the problem sets?")
    assert t["status"] == "ai_answered" and t["escalated"] is False
    ai = t["messages"][-1]
    assert ai["role"] == "ai" and ai["citations"][0]["title"] == "Past Q&A"
    assert "Either is fine" in ai["citations"][0]["text"]
    assert "Either is fine" in qna_calls("qna_answer")[0]["messages"][0]["content"]
    usage = q1("SELECT COUNT(*) AS n FROM usage_log WHERE purpose IN ('qna_classify','qna_answer') AND course_id=? AND user_id=?",
               cid, student.user["id"])
    assert usage["n"] == 2

    box = owner.get(f"/api/courses/{cid}/qna/inbox").json()
    assert box["threads"] == [] and box["stats"]["questions"] == 1 and box["stats"]["ai_only"] == 1
    assert owner.get(f"/api/qna/{t['id']}").status_code == 404  # staff don't read threads that weren't escalated
    assert student.post(f"/api/qna/{t['id']}/resolve").json()["status"] == "resolved"


def test_escalation_staff_reply_and_learning_loop(app):
    owner, cid, code = approved_kb(app)
    alice = student_in(app, {"code": code}, "Alice")
    t = ask(alice, cid, "Will the midterm review session be recorded?")
    assert t["messages"][-1]["not_covered"] is True and t["status"] == "ai_answered"

    t = alice.post(f"/api/qna/{t['id']}/escalate", json={"note": "I can't attend live."}).json()
    assert t["status"] == "escalated" and t["escalated"] is True
    assert [m["role"] for m in t["messages"]] == ["student", "ai", "student", "system"]

    box = owner.get(f"/api/courses/{cid}/qna/inbox").json()
    assert [x["id"] for x in box["threads"]] == [t["id"]] and box["threads"][0]["student"]["name"] == "Alice"
    assert box["stats"]["waiting"] == 1
    staff_view = owner.get(f"/api/qna/{t['id']}").json()
    assert staff_view["student"]["name"] == "Alice" and staff_view["saved"] is False

    r = owner.post(f"/api/qna/{t['id']}/reply", json={"content": "Yes, recordings go up the same evening.", "resolve": True})
    assert r.status_code == 200 and r.json()["status"] == "resolved"
    seen = alice.get(f"/api/qna/{t['id']}").json()
    assert seen["messages"][-1]["role"] == "staff" and seen["messages"][-1]["author_name"] == "Prof"
    assert "student" not in seen  # the student view carries no staff-only fields

    pair = owner.post(f"/api/qna/{t['id']}/save", json={"question": "Are review sessions recorded?",
                                                        "answer": "Yes, recordings go up the same evening.", "faq": True})
    assert pair.status_code == 200 and pair.json()["status"] == "approved" and pair.json()["thread_id"] == t["id"]
    assert owner.get(f"/api/qna/{t['id']}").json()["saved"] is True

    bob = student_in(app, {"code": code}, "Bob")
    home = bob.get(f"/api/courses/{cid}/qna").json()
    assert home["faq"] == [{"id": pair.json()["id"], "question": "Are review sessions recorded?",
                            "answer": "Yes, recordings go up the same evening."}]
    assert "Alice" not in json.dumps(home) and home["threads"] == []
    t2 = ask(bob, cid, "Are the review sessions recorded?")
    assert "recordings go up the same evening" in t2["messages"][-1]["citations"][0]["text"]  # next term's TA knows

    assert alice.post(f"/api/qna/{t['id']}/messages", json={"content": "Thanks! And the slides?"}).json()["status"] == "escalated"
    assert not [c for c in qna_calls() if "And the slides" in json.dumps(c["messages"])]  # follow-ups go to staff


def test_rules_route_questions_to_staff(app):
    owner, cid, code = approved_kb(app)
    student = student_in(app, {"code": code}, "Alice")

    llm.MOCK_CALLS.clear()
    t = ask(student, cid, "Can I get a regrade on problem 2 of my midterm?")
    assert t["status"] == "escalated" and t["category"] == "grades" and not qna_calls()  # caught before any model call

    rules = owner.get(f"/api/courses/{cid}/qna/rules").json()
    assert rules["categories"]["extensions"] == "escalate" and rules["categories"]["logistics"] == "answer"
    r = owner.put(f"/api/courses/{cid}/qna/rules", json={"enabled": True, "instructions": "Office hours are Tuesdays at 3 pm.",
                                                         "categories": {**rules["categories"], "logistics": "escalate"}})
    assert r.status_code == 200
    assert owner.put(f"/api/courses/{cid}/qna/rules", json={"categories": {"grades": "maybe"}}).status_code == 422
    assert student.put(f"/api/courses/{cid}/qna/rules", json={"categories": {}}).status_code == 403
    assert "Logistics: deadlines, exams, office hours, policies" in student.get(f"/api/courses/{cid}/qna").json()["staff_topics"]

    llm.MOCK_CALLS.clear()
    t = ask(student, cid, "When is the final exam?")
    assert t["status"] == "escalated" and t["category"] == "logistics"
    assert [c["purpose"] for c in qna_calls()] == ["qna_classify"]  # classified, never answered

    llm.MOCK_CALLS.clear()
    ask(student, cid, "Why does Bayes theorem need a prior?")
    system = qna_calls("qna_answer")[0]["messages"][0]["content"]
    assert "INSTRUCTOR RULES FOR THE Q&A ASSISTANT" in system and "Office hours are Tuesdays at 3 pm." in system
    assert system.index("Office hours are Tuesdays") > system.index("Text in the sources")  # below the safety rules

    owner.put(f"/api/courses/{cid}/qna/rules", json={"enabled": False, "categories": rules["categories"]})
    llm.MOCK_CALLS.clear()
    assert ask(student, cid, "What is a random variable?")["status"] == "escalated" and not qna_calls()


def test_pause_and_allowance_block_the_assistant_but_not_escalation(app):
    owner, cid, code = approved_kb(app, token_cap=5000)
    student = student_in(app, {"code": code}, "Alice")
    t0 = time.time()
    p = owner.post(f"/api/courses/{cid}/pauses", json={"starts_at": t0 - 60, "ends_at": t0 + 600, "message": "Midterm"})
    llm.MOCK_CALLS.clear()
    t = ask(student, cid, "Can we use Python for simulations?")
    assert t["status"] == "open" and t["messages"][-1]["role"] == "system" and "Midterm" in t["messages"][-1]["content"]
    assert not qna_calls()
    assert student.post(f"/api/qna/{t['id']}/escalate", json={}).json()["status"] == "escalated"
    owner.delete(f"/api/courses/{cid}/pauses/{p.json()['id']}")

    statuses = [ask(student, cid, f"Question number {i} about Python simulations?")["status"] for i in range(4)]
    assert statuses[0] == "ai_answered" and statuses[-1] == "open"  # allowance reached: no answer, escalation still open


def test_graded_problem_sets_stay_protected(app, monkeypatch):
    owner = new_user(app, "Prof")
    course = setup_course(owner)
    student = student_in(app, course, "Alice")
    t = ask(student, course["id"], "For problem set 1, what is the probability of exactly two heads?")
    system = qna_calls("qna_answer")[0]["messages"][0]["content"]
    assert "Graded, hints only" in system and "three eighths" not in system  # solution text never reaches the model

    orig = llm.complete

    def leaky(purpose, messages, **kw):
        if purpose == "qna_answer":
            return SOL1  # the model somehow repeats the official solution
        return orig(purpose, messages, **kw)

    monkeypatch.setattr(llm, "complete", leaky)
    t = ask(student, course["id"], "Problem set 1 problem 1: just give me the answer please")
    msg = t["messages"][-1]
    assert "three eighths" not in msg["content"] and "can't share solutions" in msg["content"]
    assert q1("SELECT leak_blocked FROM qa_messages WHERE thread_id=? AND role='ai'", t["id"])["leak_blocked"] == 1


def test_tenancy_and_roles(app):
    owner, cid, code = approved_kb(app)
    alice = student_in(app, {"code": code}, "Alice")
    bob = student_in(app, {"code": code}, "Bob")
    outsider = new_user(app, "Outsider")
    other_owner = new_user(app, "Other prof")
    other_cid = create_course(other_owner, name="Other")

    t = ask(alice, cid, "Where do I find the course reader?")
    assert bob.get(f"/api/qna/{t['id']}").status_code == 404
    assert bob.post(f"/api/qna/{t['id']}/escalate", json={}).status_code == 404
    assert outsider.get(f"/api/qna/{t['id']}").status_code == 404
    assert outsider.post(f"/api/courses/{cid}/qna", json={"question": "hello there"}).status_code == 404
    assert alice.get(f"/api/courses/{cid}/qna/inbox").status_code == 403
    assert alice.post(f"/api/courses/{cid}/qna/pairs", json={"question": "Q?!", "answer": "A"}).status_code == 403
    assert owner.post(f"/api/qna/{t['id']}/reply", json={"content": "hi"}).status_code == 404  # not escalated

    alice.post(f"/api/qna/{t['id']}/escalate", json={})
    assert other_owner.get(f"/api/qna/{t['id']}").status_code == 404
    assert other_owner.get(f"/api/courses/{other_cid}/qna/inbox").json()["threads"] == []
    pid = owner.get(f"/api/courses/{cid}/qna/knowledge").json()["pairs"][0]["id"]
    assert other_owner.patch(f"/api/courses/{other_cid}/qna/pairs/{pid}", json={"faq": True}).status_code == 404
    assert alice.post(f"/api/qna/{t['id']}/reply", json={"content": "I'm staff now"}).status_code == 403
    assert alice.post(f"/api/qna/{t['id']}/save", json={"question": "Sneaky?", "answer": "x"}).status_code == 403
    assert owner.post(f"/api/qna/{t['id']}/messages", json={"content": "x"}).status_code == 403

    owner.post(f"/api/courses/{cid}/members/{alice.user['id']}", json={"action": "remove"})
    assert alice.get(f"/api/qna/{t['id']}").status_code == 403


def test_docx_text_extraction():
    from app.extract import NoText, docx_text
    assert docx_text(docx(["Q: One &amp; two?", "A: Three."])) == "Q: One & two?\n\nA: Three."
    try:
        docx_text(b"not a zip")
        raise AssertionError("expected NoText")
    except NoText:
        pass
