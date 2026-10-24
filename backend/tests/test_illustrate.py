"""Tests for the Illustrate concept animation endpoint: skill routing (Anatomy, Manim 3B1B, Explainer Diagram/Video),
in-page HTML/SVG/Manim generation, download formats, tenancy, pre-turn gates, and Graded solution leak protection."""
import json
import time

from conftest import ask, new_chat, new_user, q1, setup_course, student_in


def test_illustrate_auto_routing_and_persistence(app):
    owner = new_user(app, "Prof")
    course = setup_course(owner)
    student = student_in(app, course, "Alice")
    chat_id = new_chat(student, course["id"])

    # Empty chat without prompt is rejected
    r_empty = student.post(f"/api/chats/{chat_id}/illustrate", json={})
    assert r_empty.status_code == 422

    # Ask a question first, then illustrate
    ask(student, chat_id, "Can you explain Bayes theorem and conditional probability?")
    r = student.post(f"/api/chats/{chat_id}/illustrate", json={})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["skill"] == "manim_3b1b"
    assert data["skill_meta"]["repo"] == "adithya-s-k/manim_skill"
    assert "<!DOCTYPE html>" in data["artifact_html"]
    assert "from manim import *" in data["manim_code"]
    assert len(data["spec"]["beats"]) >= 2

    # Explicitly request Anatomy isometric skill
    r_iso = student.post(
        f"/api/chats/{chat_id}/illustrate",
        json={"preferred_skill": "anatomy_isometric", "prompt": "Galton board apparatus for binomial trials"},
    )
    assert r_iso.status_code == 200, r_iso.text
    iso_data = r_iso.json()
    assert iso_data["skill"] == "anatomy_isometric"
    assert iso_data["skill_meta"]["repo"] == "wheresryan22/anatomy"

    # Explicitly request Explainer Diagram skill
    r_diag = student.post(
        f"/api/chats/{chat_id}/illustrate",
        json={"preferred_skill": "explainer_diagram", "prompt": "Hypothesis test step-by-step workflow"},
    )
    assert r_diag.status_code == 200, r_diag.text
    assert r_diag.json()["skill"] == "explainer_diagram"

    # Explicitly request Remotion Motion Graphics skill
    r_rem = student.post(
        f"/api/chats/{chat_id}/illustrate",
        json={"preferred_skill": "remotion_motion", "prompt": "Kinetic motion graphics breakdown of expected value metrics"},
    )
    assert r_rem.status_code == 200, r_rem.text
    rem_data = r_rem.json()
    assert rem_data["skill"] == "remotion_motion"
    assert rem_data["skill_meta"]["repo"] == "haidrrrry/claude-remotion-skill"
    assert "renderRemotionMotion" in rem_data["artifact_html"]

    # Check persistence in GET /api/chats/{chat_id} and GET /api/chats/{chat_id}/illustrations
    chat_res = student.get(f"/api/chats/{chat_id}").json()
    assert len(chat_res["illustrations"]) == 4
    list_res = student.get(f"/api/chats/{chat_id}/illustrations").json()
    assert [x["id"] for x in list_res] == [rem_data["id"], r_diag.json()["id"], iso_data["id"], data["id"]]

    # Verify usage attribution was logged with course_id, user_id, chat_id
    usage = q1(
        "SELECT COUNT(*) AS n FROM usage_log WHERE course_id=? AND user_id=? AND chat_id=? AND purpose IN ('illustrate_route','illustrate_gen')",
        course["id"],
        student.user["id"],
        chat_id,
    )
    assert usage["n"] >= 4


def test_illustrate_download_formats_and_tenancy(app):
    owner = new_user(app, "Prof")
    course = setup_course(owner)
    alice = student_in(app, course, "Alice")
    bob = student_in(app, course, "Bob")
    outsider = new_user(app, "Outsider")

    chat_id = new_chat(alice, course["id"])
    ask(alice, chat_id, "Explain expectation and variance")
    ill = alice.post(f"/api/chats/{chat_id}/illustrate", json={}).json()
    ill_id = ill["id"]

    # Download HTML, SVG, and Manim Python script
    r_html = alice.get(f"/api/illustrations/{ill_id}/download?format=html")
    assert r_html.status_code == 200
    assert "text/html" in r_html.headers["content-type"]
    assert "attachment;" in r_html.headers["content-disposition"]
    assert "<!DOCTYPE html>" in r_html.text

    r_svg = alice.get(f"/api/illustrations/{ill_id}/download?format=svg")
    assert r_svg.status_code == 200
    assert "image/svg+xml" in r_svg.headers["content-type"]
    assert "<svg" in r_svg.text

    r_py = alice.get(f"/api/illustrations/{ill_id}/download?format=py")
    assert r_py.status_code == 200
    assert "from manim import *" in r_py.text

    # Invalid format returns 422
    assert alice.get(f"/api/illustrations/{ill_id}/download?format=exe").status_code == 422

    # Tenancy: another student or outsider cannot access Alice's chat illustrations or downloads
    assert bob.get(f"/api/chats/{chat_id}/illustrations").status_code == 404
    assert bob.post(f"/api/chats/{chat_id}/illustrate", json={"prompt": "test"}).status_code == 404
    assert bob.get(f"/api/illustrations/{ill_id}/download?format=html").status_code == 404
    assert outsider.get(f"/api/illustrations/{ill_id}/download?format=html").status_code == 404


def test_illustrate_respects_pause_and_allowance_gates(app):
    owner = new_user(app, "Prof")
    course = setup_course(owner, token_cap=5000)
    student = student_in(app, course, "Student")
    chat_id = new_chat(student, course["id"])
    ask(student, chat_id, "Explain Bayes theorem")

    # 1. Pause gate (423)
    now_ts = time.time()
    p = owner.post(
        f"/api/courses/{course['id']}/pauses",
        json={"starts_at": now_ts - 60, "ends_at": now_ts + 600, "message": "Midterm exam in progress"},
    )
    assert p.status_code == 200
    r_paused = student.post(f"/api/chats/{chat_id}/illustrate", json={})
    assert r_paused.status_code == 423
    owner.delete(f"/api/courses/{course['id']}/pauses/{p.json()['id']}")

    # 2. Student token allowance gate (429)
    r_ok = student.post(f"/api/chats/{chat_id}/illustrate", json={})
    assert r_ok.status_code == 200
    r_ok2 = student.post(f"/api/chats/{chat_id}/illustrate", json={})
    assert r_ok2.status_code in (200, 429)
    r_cap = student.post(f"/api/chats/{chat_id}/illustrate", json={})
    assert r_cap.status_code == 429


def test_illustrate_blocks_graded_solution_leak(app, monkeypatch):
    from app import llm

    owner = new_user(app, "Prof")
    course = setup_course(owner)
    student = student_in(app, course, "Student")
    chat_id = new_chat(student, course["id"], kind="pset", doc_id=course["p1"])
    ask(student, chat_id, "Help me with Problem 1 on tossing a fair coin three times.")

    orig_complete = llm.complete

    def leaky_complete(purpose, messages, **kw):
        if purpose == "illustrate_gen":
            # Attempt to leak verbatim solution phrase from SOL1
            return json.dumps({
                "title": "Solution 1 Leak",
                "subtitle": "The probability of exactly two heads equals three eighths because the three favorable sequences HHT HTH THH appear among eight equally likely outcomes",
                "formula": "3/8",
                "beats": [
                    {
                        "step": 1,
                        "heading": "Exact Answer",
                        "caption": "The probability of exactly two heads equals three eighths because the three favorable sequences HHT HTH THH appear among eight equally likely outcomes.",
                        "highlight": "3/8",
                    }
                ],
            })
        return orig_complete(purpose, messages, **kw)

    monkeypatch.setattr(llm, "complete", leaky_complete)
    r = student.post(f"/api/chats/{chat_id}/illustrate", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    # The leak guard must strip the leaked solution text and replace with safe conceptual guidance
    assert "three eighths" not in body["artifact_html"].lower()
    assert "HHT HTH THH" not in body["artifact_html"]
    assert "Concept Intuition" in body["title"]


def test_illustration_after_a_follow_up_uses_the_rewritten_query_and_embeddings(app, monkeypatch):
    """Regression: illustrations used to search with the raw last message ("why?") and BM25 only."""
    from app import llm

    owner = new_user(app, "Prof")
    course = setup_course(owner)
    student = student_in(app, course, "Student")
    chat_id = new_chat(student, course["id"])
    ask(student, chat_id, "Why does Bayes theorem need a prior?")
    ask(student, chat_id, "why?")
    real = llm._mock_complete
    rewrites = []

    def fake(purpose, messages, attr):
        if purpose == "rewrite":
            rewrites.append(messages[-1]["content"])
            return "why does Bayes theorem need a prior"
        return real(purpose, messages, attr)

    monkeypatch.setattr(llm, "_mock_complete", fake)
    r = student.post(f"/api/chats/{chat_id}/illustrate", json={})
    assert r.status_code == 200, r.text
    assert rewrites and "LATEST MESSAGE: why?" in rewrites[-1] and "Bayes theorem need a prior" in rewrites[-1]
    gen = [c for c in llm.MOCK_CALLS if c["purpose"] == "illustrate_gen"][-1]
    assert "Lecture 3 - Bayes" in gen["messages"][1]["content"].split("COURSE MATERIALS:")[1]
    embedded = q1("SELECT COUNT(*) AS n FROM usage_log WHERE purpose='embed_query' AND chat_id=?", chat_id)
    assert embedded["n"] >= 3  # two tutor turns and the illustration
