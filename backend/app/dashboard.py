"""Staff dashboard (PRD §3.6): aggregates only, never a student's chats.

Preview chats are excluded. With fewer than SMALL_GROUP_MIN active students in the range, the materials,
unanswered and stuck panels are hidden; a problem set row with fewer students than that is hidden too."""
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from . import config
from .courses import Member, course_tokens, get_staff, term_start
from .db import db, now
from .knowledge import KIND_LABELS

router = APIRouter()

RANGES = {"7d": 7 * 86400, "30d": 30 * 86400}
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")


def _hidden(reason_count: int) -> dict:
    return {"hidden": True, "reason": f"Not enough students yet to show this without identifying anyone "
                                      f"(needs {config.SMALL_GROUP_MIN}, has {reason_count})."}


@router.get("/api/courses/{course_id}/dashboard")
def dashboard(span: str = Query(default="7d", alias="range"), tz_offset: int = Query(default=0, ge=-840, le=840),
              m: Member = Depends(get_staff)):
    if span not in (*RANGES, "term"):
        raise HTTPException(422, "Range must be 7d, 30d or term")
    c = m.course
    since = term_start(c) if span == "term" else now() - RANGES[span]
    with db() as conn:
        qs = conn.execute("SELECT m.user_id, m.content, m.created_at, m.doc_ids, m.problem_doc_id, m.attempt_status, "
                          "m.not_covered FROM messages m WHERE m.course_id=? AND m.role='user' AND m.is_preview=0 "
                          "AND m.created_at>=? ORDER BY m.created_at", (c["id"], since)).fetchall()
        students = conn.execute("SELECT u.id, u.name, u.is_sample FROM memberships ms JOIN users u ON u.id=ms.user_id "
                                "WHERE ms.course_id=? AND ms.role='student'", (c["id"],)).fetchall()
        seats_used = conn.execute("SELECT COUNT(*) AS n FROM memberships WHERE course_id=? AND role='student' "
                                  "AND status='active'", (c["id"],)).fetchone()["n"]
        tokens = {r["user_id"]: int(r["n"] or 0) for r in conn.execute(
            "SELECT user_id, COALESCE(SUM(total_tokens),0) AS n FROM usage_log WHERE course_id=? AND ts>=? "
            "GROUP BY user_id", (c["id"], since)).fetchall()}
        titles = {r["id"]: (r["title"], r["kind"]) for r in conn.execute(
            "SELECT id, title, kind FROM documents WHERE course_id=?", (c["id"],)).fetchall()}
        total_tokens = course_tokens(conn, c)

    student_ids = {s["id"] for s in students}
    qs = [q for q in qs if q["user_id"] in student_ids]  # staff questions outside preview chats don't count either
    active = {q["user_id"] for q in qs}
    small = len(active) < config.SMALL_GROUP_MIN

    tz = timezone(timedelta(minutes=-tz_offset))  # the browser's getTimezoneOffset() is minutes behind UTC
    per_day = Counter(datetime.fromtimestamp(q["created_at"], tz).date().isoformat() for q in qs)
    start = datetime.fromtimestamp(since, tz).date()
    days = [(start + timedelta(days=i)).isoformat() for i in range((datetime.fromtimestamp(now(), tz).date() - start).days + 1)]

    overview = {"active_students": len(active), "questions": len(qs),
                "questions_per_day": [{"date": d, "count": per_day.get(d, 0)} for d in days[-90:]],
                "seats_used": seats_used, "student_seats": c["student_seats"],
                "tokens_used": total_tokens, "token_ceiling": c["token_ceiling"]}

    if small:
        materials = unanswered = stuck = _hidden(len(active))
    else:
        cited = Counter(d for q in qs for d in json.loads(q["doc_ids"] or "[]"))
        materials = {"hidden": False, "items": [
            {"doc_id": d, "title": titles.get(d, ("(deleted)", ""))[0],
             "kind": KIND_LABELS.get(titles.get(d, ("", ""))[1], ""), "questions": n} for d, n in cited.most_common(10)]}
        unanswered = {"hidden": False, "items": [
            {"text": EMAIL.sub("[email]", q["content"])[:300], "at": q["created_at"]}
            for q in reversed(qs) if q["not_covered"]][:25]}
        by_set: dict[str, list] = defaultdict(list)
        for q in qs:
            if q["problem_doc_id"]:
                by_set[q["problem_doc_id"]].append(q)
        rows, hidden_sets = [], 0
        for pid, items in by_set.items():
            who = {q["user_id"] for q in items}
            if len(who) < config.SMALL_GROUP_MIN:
                hidden_sets += 1
                continue
            results = Counter(q["attempt_status"] for q in items if q["attempt_status"] in ("correct", "partially", "incorrect"))
            rows.append({"doc_id": pid, "title": titles.get(pid, ("(deleted)", ""))[0], "students": len(who),
                         "questions_per_student": round(len(items) / len(who), 1),
                         "correct": results.get("correct", 0), "partial": results.get("partially", 0),
                         "incorrect": results.get("incorrect", 0)})
        stuck = {"hidden": False, "items": sorted(rows, key=lambda r: -r["students"]), "hidden_sets": hidden_sets}

    asked = Counter(q["user_id"] for q in qs)
    usage = sorted(({"user_id": s["id"], "name": s["name"], "questions": asked.get(s["id"], 0),
                     "tokens": tokens.get(s["id"], 0)} for s in students if asked.get(s["id"]) or tokens.get(s["id"])),
                   key=lambda r: (-r["tokens"], r["name"]))
    return {"range": span, "since": since, "overview": overview, "materials": materials, "unanswered": unanswered,
            "stuck": stuck, "students": usage, "sample_data": any(s["is_sample"] for s in students)}
