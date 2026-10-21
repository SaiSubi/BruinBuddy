"""Roster (remove, block, unblock) and single-use staff codes (PRD §2.4–2.5)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .courses import Member, get_owner, get_staff, hash_code, new_staff_code
from .db import db, now

router = APIRouter()

STAFF_CODE_TTL = 7 * 86400


@router.get("/api/courses/{course_id}/members")
def roster(m: Member = Depends(get_staff)):
    cid = m.course["id"]
    with db() as conn:
        rows = conn.execute(
            "SELECT u.id, u.name, u.email, u.is_sample, ms.role, ms.status, ms.created_at FROM memberships ms "
            "JOIN users u ON u.id=ms.user_id WHERE ms.course_id=? ORDER BY ms.role, u.name", (cid,)).fetchall()
        questions = {r["user_id"]: r["n"] for r in conn.execute(
            "SELECT user_id, COUNT(*) AS n FROM messages WHERE course_id=? AND role='user' AND is_preview=0 "
            "GROUP BY user_id", (cid,)).fetchall()}
        tokens = {r["user_id"]: r["n"] for r in conn.execute(
            "SELECT user_id, COALESCE(SUM(total_tokens),0) AS n FROM usage_log WHERE course_id=? GROUP BY user_id",
            (cid,)).fetchall()}
        pending = conn.execute("SELECT COUNT(*) AS n FROM staff_codes WHERE course_id=? AND used_by IS NULL "
                               "AND revoked_at IS NULL AND expires_at>?", (cid, now())).fetchone()["n"]
    people = [{"user_id": r["id"], "name": r["name"], "email": r["email"], "role": r["role"], "status": r["status"],
               "joined_at": r["created_at"], "sample": bool(r["is_sample"]),
               "questions": questions.get(r["id"], 0), "tokens": int(tokens.get(r["id"], 0) or 0)} for r in rows]
    students = [p for p in people if p["role"] == "student"]
    staff = [p for p in people if p["role"] != "student" and p["status"] == "active"]
    return {"students": students, "staff": staff,
            "seats": {"students": sum(p["status"] == "active" for p in students), "student_seats": m.course["student_seats"],
                      "staff": sum(p["role"] == "staff" for p in staff), "staff_seats": m.course["staff_seats"],
                      "pending_codes": pending}}


class MemberAction(BaseModel):
    action: str  # remove | block | unblock


@router.post("/api/courses/{course_id}/members/{user_id}")
def member_action(user_id: int, body: MemberAction, m: Member = Depends(get_staff)):
    if body.action not in ("remove", "block", "unblock"):
        raise HTTPException(422, "Unknown action")
    if user_id == m.user["id"]:
        raise HTTPException(422, "You can't change your own membership.")
    cid = m.course["id"]
    with db() as conn:
        target = conn.execute("SELECT role, status FROM memberships WHERE course_id=? AND user_id=?",
                              (cid, user_id)).fetchone()
        if not target:
            raise HTTPException(404, "That person isn't in this course.")
        if target["role"] == "owner":
            raise HTTPException(403, "The course owner can't be removed.")
        if target["role"] == "staff":
            if m.role != "owner":
                raise HTTPException(403, "Only the course owner can remove staff.")
            if body.action != "remove":
                raise HTTPException(422, "Staff can be removed, not blocked.")
        status = {"remove": "removed", "block": "blocked", "unblock": "removed"}[body.action]
        if body.action == "unblock" and target["status"] != "blocked":
            raise HTTPException(422, "That student isn't blocked.")
        conn.execute("UPDATE memberships SET status=?, updated_at=? WHERE course_id=? AND user_id=?",
                     (status, now(), cid, user_id))
    return {"ok": True, "status": status}


def _code_status(r) -> str:
    if r["used_by"]:
        return "used"
    if r["revoked_at"]:
        return "revoked"
    return "expired" if r["expires_at"] <= now() else "pending"


@router.get("/api/courses/{course_id}/staff-codes")
def list_staff_codes(m: Member = Depends(get_owner)):
    with db() as conn:
        rows = conn.execute("SELECT s.id, s.last4, s.created_at, s.expires_at, s.used_by, s.used_at, s.revoked_at, "
                            "u.name AS used_by_name FROM staff_codes s LEFT JOIN users u ON u.id=s.used_by "
                            "WHERE s.course_id=? ORDER BY s.created_at DESC", (m.course["id"],)).fetchall()
    return [{"id": r["id"], "last4": r["last4"], "created_at": r["created_at"], "expires_at": r["expires_at"],
             "status": _code_status(r), "used_by_name": r["used_by_name"]} for r in rows]


@router.post("/api/courses/{course_id}/staff-codes")
def create_staff_code(m: Member = Depends(get_owner)):
    cid = m.course["id"]
    with db() as conn:
        staff = conn.execute("SELECT COUNT(*) AS n FROM memberships WHERE course_id=? AND role='staff' AND status='active'",
                             (cid,)).fetchone()["n"]
        pending = conn.execute("SELECT COUNT(*) AS n FROM staff_codes WHERE course_id=? AND used_by IS NULL "
                               "AND revoked_at IS NULL AND expires_at>?", (cid, now())).fetchone()["n"]
        if staff + pending >= m.course["staff_seats"]:
            raise HTTPException(409, f"Your plan includes {m.course['staff_seats']} staff accounts, and they're all "
                                     "used or reserved by unused codes. Revoke a code or remove a staff member first.")
        code = new_staff_code()
        expires = now() + STAFF_CODE_TTL
        cur = conn.execute("INSERT INTO staff_codes(course_id,code_hash,last4,created_by,created_at,expires_at) "
                           "VALUES(?,?,?,?,?,?) RETURNING id", (cid, hash_code(code), code[-4:], m.user["id"], now(), expires))
        code_id = cur.fetchone()["id"]
    return {"id": code_id, "code": code, "expires_at": expires}


@router.delete("/api/courses/{course_id}/staff-codes/{code_id}")
def revoke_staff_code(code_id: int, m: Member = Depends(get_owner)):
    with db() as conn:
        row = conn.execute("UPDATE staff_codes SET revoked_at=? WHERE id=? AND course_id=? AND used_by IS NULL "
                           "AND revoked_at IS NULL RETURNING id", (now(), code_id, m.course["id"])).fetchone()
    if not row:
        raise HTTPException(409, "Only an unused code can be revoked.")
    return {"ok": True}
