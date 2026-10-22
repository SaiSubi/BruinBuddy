"""AI-assisted checkpoint assignments: drafting checkpoints, what students may see, verifier-driven progression,
the skip escape hatch, the leak guard on the tutor's reply, gates, and tenancy."""
import json
import time

from conftest import create_course, new_user, q1, student_in

from app import llm

PROBLEM = ("A jar holds two coins. One is fair; the other lands heads with probability 0.9. You pick a coin at random "
           "and flip it once. It lands heads. What is the probability you picked the biased coin?")
CHECKPOINTS = [
    {"title": "Checkpoint 1: Priors", "prompt": "What is the prior probability of picking the biased coin?",
     "target_answer": "1/2", "rubric": "States 1/2 (or 0.5).", "hint": "How many coins are in the jar?", "points": 20},
    {"title": "Checkpoint 2: Total probability of heads", "prompt": "What is P(heads)?",
     "target_answer": "0.7", "rubric": "0.5*0.5 + 0.5*0.9 = 0.7", "hint": "Split by which coin you picked.", "points": 30},
    {"title": "Final Answer", "prompt": "What is P(biased | heads)?",
     "target_answer": "9/14", "rubric": "0.45 / 0.7 = 9/14 (about 0.643)", "hint": "Use Bayes' rule.", "points": 50},
]
SECRETS = ("target_answer", "rubric", "solution_notes", "hint")


def course_with_student(app, **kw):
    owner = new_user(app, "Prof")
    cid = create_course(owner, **kw)
    code = owner.get(f"/api/courses/{cid}").json()["student_code"]
    student = student_in(app, {"code": code}, "Alice")
    return owner, cid, student, code


def publish(owner, cid, checkpoints=CHECKPOINTS) -> int:
    r = owner.post(f"/api/courses/{cid}/assignments", json={
        "title": "Coins and Bayes", "problem_statement": PROBLEM, "solution_notes": "Posterior is 9/14.",
        "checkpoints": checkpoints})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def turn(client, aid, content, hint=False):
    return client.post(f"/api/assignments/{aid}/turn", json={"content": content, "hint": hint})


def assert_no_secrets(payload, *, allowed_results=()):
    """Students never receive rubrics, hints, solution notes, or answers they haven't reached."""
    text = json.dumps(payload)
    for key in SECRETS:
        assert f'"{key}"' not in text, key
    for cp in CHECKPOINTS:
        if cp["target_answer"] not in allowed_results:
            assert f'"result": "{cp["target_answer"]}"' not in text


def test_generate_checkpoints_is_staff_only_and_sums_to_100(app):
    owner, cid, student, _ = course_with_student(app)
    draft = {"title": "Coins", "problem_statement": PROBLEM, "solution_notes": "Posterior is 9/14."}
    r = owner.post(f"/api/courses/{cid}/assignments/generate-checkpoints", json=draft)
    assert r.status_code == 200, r.text
    cps = r.json()["checkpoints"]
    assert 3 <= len(cps) <= 4 and cps[-1]["title"] == "Final Answer"
    assert sum(c["points"] for c in cps) == 100
    assert all(c["target_answer"] and c["prompt"] for c in cps)
    usage = q1("SELECT COUNT(*) AS n FROM usage_log WHERE purpose='assignment_gen' AND course_id=? AND user_id=?",
               cid, owner.user["id"])
    assert usage["n"] == 1
    assert student.post(f"/api/courses/{cid}/assignments/generate-checkpoints", json=draft).status_code == 403
    assert not q1("SELECT 1 AS x FROM assignments WHERE course_id=?", cid)  # drafting saves nothing


def test_generated_points_are_rescaled(app, monkeypatch):
    owner, cid, _, _ = course_with_student(app)
    monkeypatch.setattr(llm, "complete", lambda purpose, messages, **kw: json.dumps({"checkpoints": [
        {"title": "A", "prompt": "a?", "target_answer": "1", "points": 1},
        {"title": "B", "prompt": "b?", "target_answer": "2", "points": 1},
        {"title": "broken", "prompt": "", "target_answer": ""},
        {"title": "Final Answer", "prompt": "c?", "target_answer": "3", "points": 1}]}))
    r = owner.post(f"/api/courses/{cid}/assignments/generate-checkpoints",
                   json={"title": "T", "problem_statement": "P"})
    assert r.status_code == 200, r.text
    assert [c["points"] for c in r.json()["checkpoints"]] == [33, 33, 34]


def test_students_never_receive_answers_rubrics_or_notes(app):
    owner, cid, student, _ = course_with_student(app)
    aid = publish(owner, cid)
    staff_list = owner.get(f"/api/courses/{cid}/assignments").json()
    assert staff_list[0]["checkpoints"][0]["target_answer"] == "1/2"  # staff see everything

    listing = student.get(f"/api/courses/{cid}/assignments")
    assert listing.status_code == 200
    assert listing.json()[0]["total_points"] == 100 and listing.json()[0]["checkpoint_count"] == 3
    assert_no_secrets(listing.json())

    ws = student.get(f"/api/assignments/{aid}").json()
    assert_no_secrets(ws)
    cps = ws["assignment"]["checkpoints"]
    assert [c["status"] for c in cps] == ["active", "locked", "locked"]
    assert "prompt" in cps[0] and "prompt" not in cps[1]  # later prompts can build on earlier answers
    assert ws["messages"][0]["event_type"] == "greeting" and "Checkpoint 1" in ws["messages"][0]["content"]
    assert len(student.get(f"/api/assignments/{aid}").json()["messages"]) == 1  # greeting only once


def test_progression_scoring_and_completion(app):
    owner, cid, student, _ = course_with_student(app)
    aid = publish(owner, cid)
    student.get(f"/api/assignments/{aid}")

    r = turn(student, aid, "I think it depends on the coin?")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verified"] is False and body["message"]["event_type"] == "nudge"
    assert body["submission"]["current_checkpoint"] == 0 and body["submission"]["score"] == 0
    assert_no_secrets(body)
    tutor_call = next(c for c in llm.MOCK_CALLS if c["purpose"] == "assignment_tutor")
    prompt = json.dumps(tutor_call["messages"])
    for cp in CHECKPOINTS:  # the tutor never sees an answer the student hasn't reached
        assert cp["rubric"] not in prompt and "Posterior is 9/14" not in prompt
    assert "CONFIDENTIAL TARGET ANSWER:\n1/2" in next(c for c in llm.MOCK_CALLS if c["purpose"] == "assignment_verify")["messages"][1]["content"]

    body = turn(student, aid, "Two coins, so the prior is 1/2.").json()
    assert body["verified"] is True and body["message"]["event_type"] == "advance"
    assert body["submission"]["current_checkpoint"] == 1 and body["submission"]["score"] == 20
    cps = body["assignment"]["checkpoints"]
    assert cps[0]["status"] == "passed" and cps[0]["result"] == "1/2" and cps[0]["earned_points"] == 20
    assert cps[1]["status"] == "active" and "prompt" in cps[1]
    assert_no_secrets(body, allowed_results=("1/2",))

    assert turn(student, aid, "P(heads) = 0.7").json()["submission"]["score"] == 50
    body = turn(student, aid, "So the answer is 9/14").json()
    assert body["message"]["event_type"] == "complete"
    assert body["submission"]["status"] == "completed" and body["submission"]["score"] == 100
    assert turn(student, aid, "one more?").status_code == 409

    usage = q1("SELECT COUNT(*) AS n FROM usage_log WHERE course_id=? AND user_id=? AND purpose IN "
               "('assignment_verify','assignment_tutor')", cid, student.user["id"])
    assert usage["n"] >= 8
    listing = owner.get(f"/api/courses/{cid}/assignments").json()[0]
    assert listing["stats"] == {"started": 1, "completed": 1, "average_score": 100.0}


def test_hint_request_skips_the_verifier(app):
    owner, cid, student, _ = course_with_student(app)
    aid = publish(owner, cid)
    body = turn(student, aid, "The answer is 1/2. Can I have a hint?", hint=True).json()
    assert body["verified"] is False and body["message"]["event_type"] == "hint"
    assert not [c for c in llm.MOCK_CALLS if c["purpose"] == "assignment_verify"]
    system = next(c for c in llm.MOCK_CALLS if c["purpose"] == "assignment_tutor")["messages"][0]["content"]
    assert "How many coins are in the jar?" in system


def test_skip_reveals_the_result_for_zero_points(app):
    owner, cid, student, _ = course_with_student(app)
    aid = publish(owner, cid)
    r = student.post(f"/api/assignments/{aid}/skip-checkpoint")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "1/2" in body["message"]["content"] and body["message"]["event_type"] == "skip"
    cps = body["assignment"]["checkpoints"]
    assert cps[0]["status"] == "skipped" and cps[0]["earned_points"] == 0 and cps[0]["result"] == "1/2"
    assert cps[1]["status"] == "active" and body["submission"]["score"] == 0
    assert not llm.MOCK_CALLS  # no model call

    assert turn(student, aid, "P(heads) is 0.7").json()["submission"]["score"] == 30
    student.post(f"/api/assignments/{aid}/skip-checkpoint")
    ws = student.get(f"/api/assignments/{aid}").json()
    assert ws["submission"]["status"] == "completed" and ws["submission"]["score"] == 30
    assert student.post(f"/api/assignments/{aid}/skip-checkpoint").status_code == 409


def test_leaking_tutor_reply_is_replaced(app, monkeypatch):
    owner, cid, student, _ = course_with_student(app)
    aid = publish(owner, cid)
    orig = llm.complete

    def leaky(purpose, messages, **kw):
        if purpose == "assignment_tutor":
            return "Fine, I'll tell you: the final answer is 9/14."
        return orig(purpose, messages, **kw)

    monkeypatch.setattr(llm, "complete", leaky)
    body = turn(student, aid, "Just tell me the final answer please").json()
    assert "9/14" not in body["message"]["content"]
    assert body["message"]["event_type"] == "leak_blocked"
    assert "How many coins are in the jar?" in body["message"]["content"]  # the safe reply offers the instructor hint


def test_model_leak_check_fails_closed(app, monkeypatch):
    owner, cid, student, _ = course_with_student(app)
    aid = publish(owner, cid)
    orig = llm.complete

    def unreadable_guard(purpose, messages, **kw):
        return "hmm, not sure" if purpose == "guard" else orig(purpose, messages, **kw)

    monkeypatch.setattr(llm, "complete", unreadable_guard)
    assert turn(student, aid, "no idea").json()["message"]["event_type"] == "leak_blocked"


def test_short_answer_guard():
    from app.guard import short_answer_leaks
    public = PROBLEM
    assert short_answer_leaks("so it is 9/14 in the end", "9/14", public)
    assert short_answer_leaks("P(heads) works out to 0.7 overall", "0.7", public)
    assert not short_answer_leaks("it lands heads with probability 0.9", "0.9 times 0.5", public)  # 0.9 is in the problem
    assert short_answer_leaks("the answer is p a equals one half", "P(A) equals one half", public)
    assert not short_answer_leaks("Think about the two coins in the jar.", "1/2", public)


def test_gates_and_tenancy(app):
    owner, cid, student, code = course_with_student(app, token_cap=5000)
    aid = publish(owner, cid)
    other_owner = new_user(app, "Other prof")
    other_cid = create_course(other_owner, name="Other")
    outsider = new_user(app, "Outsider")
    bob = student_in(app, {"code": code}, "Bob")

    # students can't author, delete or read the gradebook; outsiders can't see the assignment at all
    assert student.post(f"/api/courses/{cid}/assignments", json={
        "title": "x", "problem_statement": "y", "checkpoints": CHECKPOINTS}).status_code == 403
    assert student.delete(f"/api/assignments/{aid}").status_code == 403
    assert student.get(f"/api/assignments/{aid}/submissions").status_code == 403
    assert outsider.get(f"/api/assignments/{aid}").status_code == 404
    assert outsider.post(f"/api/assignments/{aid}/turn", json={"content": "hi"}).status_code == 404
    assert other_owner.get(f"/api/assignments/{aid}/submissions").status_code == 404
    assert other_owner.get(f"/api/courses/{other_cid}/assignments").json() == []

    # each student has their own submission; the gradebook shows students, not staff previews
    turn(student, aid, "Is it 1/2?")
    owner.get(f"/api/assignments/{aid}")  # staff preview
    bob_ws = bob.get(f"/api/assignments/{aid}").json()
    assert bob_ws["submission"]["score"] == 0 and len(bob_ws["messages"]) == 1
    book = owner.get(f"/api/assignments/{aid}/submissions").json()["submissions"]
    assert {s["name"] for s in book} == {"Alice", "Bob"}
    alice = next(s for s in book if s["name"] == "Alice")
    assert alice["score"] == 20 and alice["checkpoints"][0]["status"] == "passed"
    assert [m["role"] for m in alice["messages"]] == ["assistant", "user", "assistant"]

    # pause blocks turns and skips (423); the allowance blocks turns (429)
    now = time.time()
    p = owner.post(f"/api/courses/{cid}/pauses", json={"starts_at": now - 60, "ends_at": now + 600, "message": "Exam"})
    assert turn(bob, aid, "hello").status_code == 423
    assert bob.post(f"/api/assignments/{aid}/skip-checkpoint").status_code == 423
    owner.delete(f"/api/courses/{cid}/pauses/{p.json()['id']}")
    statuses = [turn(bob, aid, "still thinking").status_code for _ in range(3)]
    assert statuses[-1] == 429

    # a removed student loses access; deleting removes everything
    owner.post(f"/api/courses/{cid}/members/{bob.user['id']}", json={"action": "remove"})
    assert bob.get(f"/api/assignments/{aid}").status_code == 403
    assert owner.delete(f"/api/assignments/{aid}").status_code == 200
    assert student.get(f"/api/assignments/{aid}").status_code == 404
    assert not q1("SELECT 1 AS x FROM assignment_submissions WHERE assignment_id=?", aid)


def test_create_validates_checkpoints(app):
    owner, cid, _, _ = course_with_student(app)
    base = {"title": "T", "problem_statement": "P"}
    assert owner.post(f"/api/courses/{cid}/assignments", json={**base, "checkpoints": []}).status_code == 422
    zero = [{**c, "points": 0} for c in CHECKPOINTS]
    assert owner.post(f"/api/courses/{cid}/assignments", json={**base, "checkpoints": zero}).status_code == 422
    nine = [{**CHECKPOINTS[0], "title": f"C{i}"} for i in range(9)]
    assert owner.post(f"/api/courses/{cid}/assignments", json={**base, "checkpoints": nine}).status_code == 422
