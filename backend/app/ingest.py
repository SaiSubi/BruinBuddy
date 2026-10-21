"""Create or update the 18.05 demo course from the local MIT OCW export.

    python -m app.ingest --owner-email you@example.edu [--owner-password ...]

Public (citable): lecture notes, readings (incl. class prep), problem sets. Tutor-only: problem set solutions,
linked to their problem set by file name. Everything else is skipped. Safe to re-run: unchanged files are skipped,
and staff settings (problem set modes, release dates) are kept.

The owner must already have an account. With local accounts (development) one is created if missing. With
Supabase Auth, sign up on the site first, then run this; re-running with another email transfers ownership.
"""
import argparse
import hashlib
import json
import re
import secrets
import sys
from collections import Counter

from . import auth, billing, config
from .courses import new_student_code
from .db import db, init_db, now
from .extract import split_page
from .knowledge import bump_content

DEMO_SLUG = "mit-18.05-demo"
DEMO_NAME = "MIT 18.05 Probability and Statistics (demo)"
DEMO_PLAN = {"student_seats": 200, "staff_seats": 5, "token_cap": 200_000, "cap_period": "week"}
INCLUDED_TYPES = {"Lecture Notes", "Readings", "Problem Sets"}


def classify(types: list[str], file_name: str) -> tuple[str | None, bool]:
    """Return (kind, tutor_only) or (None, False) if the file is not ingested."""
    t = set(types)
    is_solution = "Problem Set Solutions" in t or re.search(r"_sol\b|_sol\.", file_name) is not None
    if "Exam Solutions" in t or "Exams" in t or "Supplemental Exam Materials" in t:
        return None, False
    if is_solution and "Problem Sets" in t:
        return "solution", True
    if not (t & INCLUDED_TYPES):
        return None, False
    if "Lecture Notes" in t:
        return "lecture_notes", False
    if "Readings" in t:
        return ("class_prep" if "prep" in file_name else "reading"), False
    return "problem_set", False


def link_key(file_name: str) -> str:
    return re.sub(r"_sol(?=\.)", "", file_name)


def ensure_owner(email: str, password: str | None) -> int:
    email = email.strip().lower()
    local = config.AUTH_PROVIDER == "local"
    with db() as conn:
        row = conn.execute("SELECT id FROM users WHERE email=? AND auth_id LIKE ? ORDER BY id LIMIT 1",
                           (email, "local:%" if local else "%")).fetchone()
        if row:
            return row["id"]
        if not local:
            sys.exit(f"No account for {email} yet. Sign up on the site with that email first, then re-run.")
        pw = password or secrets.token_urlsafe(9)
        cur = conn.execute("INSERT INTO users(auth_id,email,name,password_hash,created_at) VALUES(?,?,?,?,?) RETURNING id",
                           (f"local:{secrets.token_hex(16)}", email, email.split("@")[0], auth.hash_password(pw), now()))
        if not password:
            print(f"created local account {email} with password: {pw}")
        return cur.fetchone()["id"]


def _set_role(conn, course_id: int, user_id: int, role: str) -> None:
    conn.execute("INSERT INTO memberships(course_id,user_id,role,status,created_at,updated_at) VALUES(?,?,?,?,?,?) "
                 "ON CONFLICT(course_id, user_id) DO UPDATE SET role=excluded.role, status='active', "
                 "updated_at=excluded.updated_at", (course_id, user_id, role, "active", now(), now()))


def ensure_course(owner_id: int) -> int:
    with db() as conn:
        row = conn.execute("SELECT id, owner_id FROM courses WHERE slug=?", (DEMO_SLUG,)).fetchone()
        if not row:
            q = billing.quote(**DEMO_PLAN)
            started = now() - 28 * 86400  # a term already under way, so sample data falls inside it
            cur = conn.execute(
                "INSERT INTO courses(name,slug,owner_id,status,student_seats,staff_seats,token_cap,cap_period,token_ceiling,"
                "price_cents,student_code,paid_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id",
                (DEMO_NAME, DEMO_SLUG, owner_id, "active", DEMO_PLAN["student_seats"], DEMO_PLAN["staff_seats"],
                 DEMO_PLAN["token_cap"], DEMO_PLAN["cap_period"], q["token_ceiling"], 0, new_student_code(), started, started))
            course_id = cur.fetchone()["id"]
            _set_role(conn, course_id, owner_id, "owner")
            return course_id
        course_id = row["id"]
        if row["owner_id"] != owner_id:  # transfer: the previous owner stays on as staff
            _set_role(conn, course_id, row["owner_id"], "staff")
            conn.execute("UPDATE courses SET owner_id=? WHERE id=?", (owner_id, course_id))
        _set_role(conn, course_id, owner_id, "owner")
        return course_id


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--owner-email", required=True)
    ap.add_argument("--owner-password", help="local accounts only; generated if omitted")
    args = ap.parse_args(argv)

    import pymupdf  # ingestion-only dependency

    init_db()
    course_id = ensure_course(ensure_owner(args.owner_email, args.owner_password))
    report, skipped, weak = Counter(), Counter(), []
    docs = []
    for meta_path in sorted(config.META_DIR.glob("*/data.json")):
        d = json.loads(meta_path.read_text())
        f = d.get("file") or ""
        if not f.lower().endswith(".pdf"):
            continue
        file_name = f.rsplit("/", 1)[-1]
        kind, tutor_only = classify(d.get("learning_resource_types", []), file_name)
        if d["title"].startswith("All "):  # compiled readings duplicate the individual readings
            kind = None
        if kind is None:
            skipped[tuple(d.get("learning_resource_types", [])) or ("untyped",)] += 1
            continue
        pdf = config.PDF_DIR / file_name
        if not pdf.exists():
            print(f"missing PDF: {file_name}", file=sys.stderr)
            continue
        docs.append((d["uid"], d["title"], kind, file_name, tutor_only, pdf, d.get("license", "")))
    if not docs:
        sys.exit(f"No course files found in {config.META_DIR}. Is the 18.05 export in place?")

    by_link = {link_key(fn): uid for uid, _, k, fn, to, _, _ in docs if not to}
    with db() as conn:
        for uid, title, kind, file_name, tutor_only, pdf, lic in docs:
            h = hashlib.sha256(pdf.read_bytes()).hexdigest()
            row = conn.execute("SELECT file_hash FROM documents WHERE id=?", (uid,)).fetchone()
            linked = by_link.get(link_key(file_name)) if tutor_only else None
            if linked:
                conn.execute("INSERT INTO solution_links(solution_id,pset_id) VALUES(?,?) ON CONFLICT DO NOTHING",
                             (uid, linked))
            if row and row["file_hash"] == h:
                conn.execute("UPDATE documents SET course_id=?, kind=?, tutor_only=?, linked_doc_id=?, status='ready', "
                             "rights_confirmed=1 WHERE id=?", (course_id, kind, int(tutor_only), linked, uid))
                report["unchanged"] += 1
                continue
            conn.execute("DELETE FROM chunks WHERE doc_id=?", (uid,))
            conn.execute(
                "INSERT INTO documents(id,course_id,title,kind,file_name,file_hash,tutor_only,linked_doc_id,license,status,"
                "content_type,rights_confirmed,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET course_id=excluded.course_id, title=excluded.title, kind=excluded.kind, "
                "file_name=excluded.file_name, file_hash=excluded.file_hash, tutor_only=excluded.tutor_only, "
                "linked_doc_id=excluded.linked_doc_id, license=excluded.license, status='ready', "
                "updated_at=excluded.updated_at",
                (uid, course_id, title, kind, file_name, h, int(tutor_only), linked, lic, "ready", "application/pdf", 1,
                 now(), now()))
            n_chunks, n_pages = 0, 0
            with pymupdf.open(pdf) as doc:
                for pno, page in enumerate(doc, start=1):
                    text = page.get_text("text")
                    if len(text.strip()) < 40:
                        weak.append(f"{file_name} p.{pno}")
                        continue
                    n_pages += 1
                    for c in split_page(text):
                        conn.execute("INSERT INTO chunks(doc_id,page,text,tutor_only) VALUES(?,?,?,?)",
                                     (uid, pno, c, int(tutor_only)))
                        n_chunks += 1
            conn.execute("UPDATE documents SET pages=? WHERE id=?", (n_pages, uid))
            report[f"ingested:{kind}"] += 1
            report["chunks"] += n_chunks
        bump_content(conn, course_id)

        unmatched = [r["title"] for r in conn.execute(
            "SELECT d.title FROM documents d WHERE d.course_id=? AND d.kind='solution' AND NOT EXISTS "
            "(SELECT 1 FROM solution_links l WHERE l.solution_id=d.id)", (course_id,))]
        totals = {r["tutor_only"]: r["n"] for r in conn.execute(
            "SELECT c.tutor_only, COUNT(*) AS n FROM chunks c JOIN documents d ON d.id=c.doc_id WHERE d.course_id=? "
            "GROUP BY c.tutor_only", (course_id,))}
        code = conn.execute("SELECT student_code FROM courses WHERE id=?", (course_id,)).fetchone()["student_code"]

    print(f"== Demo course {course_id}: {DEMO_NAME} ==")
    for k, v in sorted(report.items()):
        print(f"  {k}: {v}")
    print(f"  chunks  public={totals.get(0, 0)}  tutor-only={totals.get(1, 0)}")
    print(f"  skipped (out of scope): {sum(skipped.values())} files")
    print(f"  pages with little/no text: {len(weak)}")
    print(f"  solutions without a linked problem set: {unmatched}")
    print(f"  student code: {code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
