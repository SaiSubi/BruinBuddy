"""Sample students and questions for a course's dashboard (PRD §3.6). Everything created here is flagged
`is_sample`, and the dashboard says so; label it as sample data in any presentation.

    python -m app.seed [--course-slug mit-18.05-demo] [--reset]

No model calls: questions, tags and token usage are written directly.
"""
import argparse
import json
import random
import sys

from .db import db, init_db, now
from .ingest import DEMO_SLUG

STUDENTS = ["Avery", "Blake", "Casey", "Devon", "Emery", "Finley", "Harper", "Jordan"]
CONCEPT = ["Why does Bayes' theorem need a prior?", "What is the difference between independent and disjoint events?",
           "How do I compute the variance of a binomial?", "When do I use the central limit theorem?",
           "What does a p-value actually mean?", "How is a pmf different from a pdf?",
           "Can you explain conditional probability with an example?", "What should I review for the exam on expectation?",
           "Why do we divide by n-1 in the sample variance?", "How do I choose a prior for a coin?"]
NOT_COVERED = ["Is the midterm cumulative?", "When are office hours this week?", "Can I use a calculator on the exam?",
               "What's the late policy for problem sets?"]
PSET = ["I'm stuck on problem 2, how do I start?", "Is my answer of 0.3 right for problem 1?",
        "I set up the integral but can't finish it.", "Which formula do I need for part (b)?"]


def reset(conn, course_id: int) -> None:
    ids = [r["id"] for r in conn.execute("SELECT u.id FROM users u JOIN memberships m ON m.user_id=u.id "
                                         "WHERE m.course_id=? AND u.is_sample=1", (course_id,)).fetchall()]
    for uid in ids:
        conn.execute("DELETE FROM messages WHERE chat_id IN (SELECT id FROM chats WHERE user_id=?)", (uid,))
        for t in ("chats", "memberships", "memories", "usage_log"):
            conn.execute(f"DELETE FROM {t} WHERE user_id=?", (uid,))
        conn.execute("DELETE FROM users WHERE id=?", (uid,))
    print(f"removed {len(ids)} sample students")


def seed(course_id: int, rng: random.Random) -> None:
    with db() as conn:
        docs = conn.execute("SELECT id, title, kind FROM documents WHERE course_id=? AND status='ready'",
                            (course_id,)).fetchall()
        readings = [d["id"] for d in docs if d["kind"] in ("lecture_notes", "reading", "class_prep")]
        psets = [d["id"] for d in docs if d["kind"] == "problem_set"][:3]
        if not readings:
            sys.exit("The course has no ready materials to cite. Run python -m app.ingest first.")
        t_end = now()
        # sample questions go back 21 days: make sure the course's term (and its token total) covers them
        conn.execute("UPDATE courses SET paid_at=? WHERE id=? AND (paid_at IS NULL OR paid_at>?)",
                     (t_end - 28 * 86400, course_id, t_end - 28 * 86400))
        for i, name in enumerate(STUDENTS, start=1):
            uid = conn.execute("INSERT INTO users(auth_id,email,name,is_sample,created_at) VALUES(?,?,?,?,?) "
                               "ON CONFLICT(auth_id) DO UPDATE SET name=excluded.name RETURNING id",
                               (f"sample:{course_id}:{i}", f"sample-{i}@example.edu", f"{name} (sample)", 1,
                                t_end - 30 * 86400)).fetchone()["id"]
            conn.execute("INSERT INTO memberships(course_id,user_id,role,status,created_at,updated_at) VALUES(?,?,?,?,?,?) "
                         "ON CONFLICT(course_id, user_id) DO NOTHING",
                         (course_id, uid, "student", "active", t_end - 28 * 86400, t_end))
            chat = conn.execute("INSERT INTO chats(course_id,user_id,title,kind,created_at,updated_at) VALUES(?,?,?,?,?,?) "
                                "RETURNING id", (course_id, uid, "Sample chat", "chat", t_end - 21 * 86400, t_end)).fetchone()["id"]
            for _ in range(rng.randint(5, 12)):
                ts = t_end - rng.uniform(0, 21 * 86400)
                roll = rng.random()
                tags = {"doc_ids": [], "problem_doc_id": None, "attempt_status": None, "not_covered": 0}
                if roll < 0.12:
                    q = rng.choice(NOT_COVERED)
                    tags["not_covered"] = 1
                elif roll < 0.42 and psets:
                    q = rng.choice(PSET)
                    tags["problem_doc_id"] = psets[0] if rng.random() < 0.75 else rng.choice(psets)
                    tags["attempt_status"] = rng.choice(["none", "incorrect", "partially", "correct", "incorrect"])
                    tags["doc_ids"] = [tags["problem_doc_id"]]
                else:
                    q = rng.choice(CONCEPT)
                    tags["doc_ids"] = sorted(set(rng.sample(readings, k=min(len(readings), rng.randint(1, 2)))))
                conn.execute("INSERT INTO messages(chat_id,role,content,course_id,user_id,doc_ids,problem_doc_id,"
                             "attempt_status,not_covered,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                             (chat, "user", q, course_id, uid, json.dumps(tags["doc_ids"]), tags["problem_doc_id"],
                              tags["attempt_status"], tags["not_covered"], ts))
                conn.execute("INSERT INTO messages(chat_id,role,content,course_id,user_id,created_at) VALUES(?,?,?,?,?,?)",
                             (chat, "assistant", "(sample reply)", course_id, uid, ts + 5))
                p, c = rng.randint(2600, 3800), rng.randint(300, 700)
                conn.execute("INSERT INTO usage_log(ts,purpose,model,prompt_tokens,completion_tokens,cost,course_id,"
                             "user_id,chat_id,total_tokens) VALUES(?,?,?,?,?,?,?,?,?,?)",
                             (ts, "tutor", "sample", p, c, 0.0, course_id, uid, chat, p + c))
    print(f"added {len(STUDENTS)} sample students with questions over the last 21 days")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Add sample students and questions to a course's dashboard.")
    ap.add_argument("--course-slug", default=DEMO_SLUG)
    ap.add_argument("--course-id", type=int)
    ap.add_argument("--reset", action="store_true", help="remove existing sample data first")
    args = ap.parse_args(argv)
    init_db()
    with db() as conn:
        row = conn.execute("SELECT id FROM courses WHERE id=?", (args.course_id,)).fetchone() if args.course_id else \
            conn.execute("SELECT id FROM courses WHERE slug=?", (args.course_slug,)).fetchone()
        if not row:
            sys.exit("Course not found.")
        course_id = row["id"]
        existing = conn.execute("SELECT COUNT(*) AS n FROM users u JOIN memberships m ON m.user_id=u.id "
                                "WHERE m.course_id=? AND u.is_sample=1", (course_id,)).fetchone()["n"]
        if existing and not args.reset:
            print(f"course {course_id} already has {existing} sample students; use --reset to recreate them")
            return 0
        if args.reset:
            reset(conn, course_id)
    seed(course_id, random.Random(18_05))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
