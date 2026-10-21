"""Staff dashboard: aggregates only, small groups hidden, preview excluded (PRD §3.6)."""
from conftest import ask, new_chat, new_user, q1, setup_course, student_in


def _dash(owner, cid, span="term"):
    r = owner.get(f"/api/courses/{cid}/dashboard?range={span}&tz_offset=420")
    assert r.status_code == 200, r.text
    return r.json()


def test_small_groups_are_hidden(app):
    owner = new_user(app)
    c = setup_course(owner)
    s = student_in(app, c, "Solo Student")
    ask(s, new_chat(s, c["id"]), "Why does Bayes theorem need a prior?")
    d = _dash(owner, c["id"])
    assert d["overview"]["active_students"] == 1 and d["overview"]["questions"] == 1
    assert d["overview"]["seats_used"] == 1 and d["overview"]["tokens_used"] > 0
    for panel in ("materials", "unanswered", "stuck"):
        assert d[panel]["hidden"] and "needs 5" in d[panel]["reason"]
    assert d["students"][0]["name"] == "Solo Student" and d["sample_data"] is False
    assert sum(x["count"] for x in d["overview"]["questions_per_day"]) == 1


def test_panels_with_enough_students(app):
    owner = new_user(app)
    c = setup_course(owner)
    students = [student_in(app, c, f"Student {i}") for i in range(5)]
    for i, s in enumerate(students):
        ask(s, new_chat(s, c["id"]), "Why does Bayes theorem need a prior?")
        ask(s, new_chat(s, c["id"], "pset", c["p1"]), "How do I start problem 1?")
        if i < 2:
            ask(s, new_chat(s, c["id"]), "zebra quantum basketball, email me at kid@school.edu")
    preview = new_chat(owner, c["id"])
    ask(owner, preview, "zebra quantum preview question")
    d = _dash(owner, c["id"], "7d")
    assert d["overview"]["active_students"] == 5 and d["overview"]["questions"] == 12  # preview excluded
    assert not d["materials"]["hidden"] and d["materials"]["items"][0]["questions"] >= 1
    texts = [u["text"] for u in d["unanswered"]["items"]]
    assert len(texts) == 2 and all("[email]" in t and "kid@school.edu" not in t for t in texts)
    assert all("preview" not in t for t in texts)
    assert not any(k in d["unanswered"]["items"][0] for k in ("user_id", "name"))  # anonymised
    row = d["stuck"]["items"][0]
    assert row["doc_id"] == c["p1"] and row["students"] == 5 and row["questions_per_student"] == 1.0
    assert {r["name"] for r in d["students"]} == {f"Student {i}" for i in range(5)}


def test_dashboard_is_staff_only_and_validates_range(app):
    owner = new_user(app)
    c = setup_course(owner)
    s = student_in(app, c)
    assert s.get(f"/api/courses/{c['id']}/dashboard").status_code == 403
    assert owner.get(f"/api/courses/{c['id']}/dashboard?range=year").status_code == 422


def test_sample_data_seed_is_labelled(app):
    owner = new_user(app)
    c = setup_course(owner)
    from app import seed
    seed.main(["--course-id", str(c["id"])])
    d = _dash(owner, c["id"], "30d")
    assert d["sample_data"] is True and d["overview"]["active_students"] >= 5
    assert not d["materials"]["hidden"]
    assert q1("SELECT COUNT(*) AS n FROM users WHERE is_sample=1 AND email LIKE 'sample-%'")["n"] >= 8
    seed.main(["--course-id", str(c["id"]), "--reset"])  # idempotent re-seed
    assert _dash(owner, c["id"], "30d")["sample_data"] is True
