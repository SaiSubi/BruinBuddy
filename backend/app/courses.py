"""Courses as tenants: membership and roles, the course view, settings, student code and joining, guidelines,
pause windows, and the allowance and ceiling arithmetic used by the chat gates.

Every course route goes through `get_member` (or `get_staff` / `get_owner`): no active membership, no access.
A non-member gets 404 so course ids can't be probed; a removed or blocked member is told so."""
import hashlib
import json
import re
import secrets
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import billing, config, knowledge, starters
from .accounts import current_user
from .db import db, lock_row, now

router = APIRouter()

CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no I, L, O, 0, 1
PERIOD_SECONDS = {"day": 86400, "week": 7 * 86400}
REMOVED_MSG = "You no longer have access to this course. Contact your instructor if you think this is a mistake."
SETUP_STEPS = ("modes", "guidelines", "share")
DOMAIN_RE = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")


@dataclass
class Member:
    user: dict
    course: dict
    role: str

    @property
    def is_staff(self) -> bool:
        return self.role in ("owner", "staff")


def load_course(conn, course_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM courses WHERE id=?", (course_id,)).fetchone()
    return dict(row) if row else None


def member_of(conn, course_id: int, user: dict) -> Member:
    course = load_course(conn, course_id)
    m = conn.execute("SELECT role, status FROM memberships WHERE course_id=? AND user_id=?",
                     (course_id, user["id"])).fetchone() if course else None
    if not m:
        raise HTTPException(404, "Course not found")
    if m["status"] != "active":
        raise HTTPException(403, REMOVED_MSG)
    return Member(user=user, course=course, role=m["role"])


def get_member(course_id: int, user: dict = Depends(current_user)) -> Member:
    with db() as conn:
        return member_of(conn, course_id, user)


def get_staff(m: Member = Depends(get_member)) -> Member:
    if not m.is_staff:
        raise HTTPException(403, "Only course staff can do that.")
    return m


def get_owner(m: Member = Depends(get_member)) -> Member:
    if m.role != "owner":
        raise HTTPException(403, "Only the course owner can do that.")
    return m


# ---- codes -------------------------------------------------------------------------------------
def _random(n: int) -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(n))


def new_student_code() -> str:
    return f"{_random(4)}-{_random(4)}"


def new_staff_code() -> str:
    return f"STAFF-{_random(4)}-{_random(4)}-{_random(4)}"


def normalize_code(raw: str) -> str:
    s = re.sub(r"[^A-Z0-9]", "", raw.upper())
    if s.startswith("STAFF") and len(s) == 17:
        return f"STAFF-{s[5:9]}-{s[9:13]}-{s[13:17]}"
    if len(s) == 8:
        return f"{s[:4]}-{s[4:]}"
    return s


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


# ---- limits ----------------------------------------------------------------------------------------
def term_start(c: dict) -> float:
    return c.get("paid_at") or c["created_at"]


def allowance(conn, c: dict, user_id: int) -> dict:
    period = c["cap_period"]
    since = term_start(c) if period == "term" else now() - PERIOD_SECONDS.get(period, PERIOD_SECONDS["week"])
    row = conn.execute("SELECT COALESCE(SUM(total_tokens),0) AS used, MIN(ts) AS oldest FROM usage_log "
                       "WHERE course_id=? AND user_id=? AND ts>?", (c["id"], user_id, since)).fetchone()
    used, cap = int(row["used"] or 0), int(c["token_cap"])
    reached = used >= cap
    frees_at = None
    if reached and period != "term" and row["oldest"]:
        frees_at = row["oldest"] + PERIOD_SECONDS.get(period, PERIOD_SECONDS["week"])
    return {"used": used, "cap": cap, "period": period, "percent": min(100, round(100 * used / cap)) if cap else 100,
            "reached": reached, "frees_at": frees_at}


def course_tokens(conn, c: dict) -> int:
    row = conn.execute("SELECT COALESCE(SUM(total_tokens),0) AS n FROM usage_log WHERE course_id=? AND ts>=?",
                       (c["id"], term_start(c))).fetchone()
    return int(row["n"] or 0)


def pause_state(conn, course_id: int) -> dict:
    t = now()
    rows = conn.execute("SELECT id, starts_at, ends_at, message FROM pauses WHERE course_id=? AND ends_at>? "
                        "ORDER BY starts_at", (course_id, t)).fetchall()
    active = next((r for r in rows if r["starts_at"] <= t), None)
    if active:
        return {"active": True, "until": active["ends_at"], "message": active["message"]}
    upcoming = next((r for r in rows if r["starts_at"] > t), None)
    return {"active": False, "next": {"starts_at": upcoming["starts_at"], "ends_at": upcoming["ends_at"],
                                      "message": upcoming["message"]} if upcoming else None}


# ---- course view --------------------------------------------------------------------------------
def _checklist(conn, c: dict, kb) -> list[dict]:
    setup = json.loads(c["setup"] or "{}")
    counts = {r["status"]: r["n"] for r in conn.execute(
        "SELECT status, COUNT(*) AS n FROM documents WHERE course_id=? GROUP BY status", (c["id"],)).fetchall()}
    previewed = conn.execute("SELECT 1 FROM chats WHERE course_id=? AND is_preview=1 LIMIT 1", (c["id"],)).fetchone()
    psets = kb.psets()
    attention = counts.get("failed", 0) + counts.get("no_text", 0)
    return [
        {"step": "materials", "done": kb.has_material,
         "detail": f"{counts.get('ready', 0)} ready, {counts.get('processing', 0)} processing"
                   + (f", {attention} need attention" if attention else "")},
        {"step": "modes", "done": bool(setup.get("modes")),
         "detail": f"{len(psets)} problem sets" + (", all Graded" if psets and all(p.set_mode == "graded" for p in psets) else "")},
        {"step": "guidelines", "done": bool(setup.get("guidelines")), "detail": ""},
        {"step": "preview", "done": previewed is not None, "detail": ""},
        {"step": "share", "done": bool(setup.get("share")), "detail": c["student_code"] or ""},
    ]


@router.get("/api/courses/{course_id}")
def course_view(m: Member = Depends(get_member)):
    c = m.course
    kb = knowledge.cache.get(c["id"])
    out = {"id": c["id"], "name": c["name"], "role": m.role, "status": c["status"],
           "open": c["status"] == "active" and kb.has_material, "starter_questions": []}
    with db() as conn:
        out["pause"] = pause_state(conn, c["id"])
        if m.role == "student":
            out["allowance"] = allowance(conn, c, m.user["id"])
        if m.is_staff:
            seats = conn.execute("SELECT role, COUNT(*) AS n FROM memberships WHERE course_id=? AND status='active' "
                                 "GROUP BY role", (c["id"],)).fetchall()
            by_role = {r["role"]: r["n"] for r in seats}
            out.update({
                "student_code": c["student_code"], "code_expires_at": c["code_expires_at"],
                "email_domain": c["email_domain"] or "",
                "plan": {"student_seats": c["student_seats"], "staff_seats": c["staff_seats"],
                         "token_cap": c["token_cap"], "cap_period": c["cap_period"], "token_ceiling": c["token_ceiling"]},
                "seats_used": {"students": by_role.get("student", 0), "staff": by_role.get("staff", 0)},
                "tokens_used": course_tokens(conn, c),
                "setup": _checklist(conn, c, kb),
            })
        if m.role == "owner":
            out["billing"] = {"price_cents": c["price_cents"], "paid_at": c["paid_at"], "mode": config.billing_mode()}
    if kb.has_material:
        starters.ensure(c["id"], c["content_version"], c["starter_version"])
        out["starter_questions"] = json.loads(c["starter_questions"] or "[]")
    return out


# ---- create, settings, code ---------------------------------------------------------------------
class CourseIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    student_seats: int
    staff_seats: int
    token_cap: int
    cap_period: str = "week"


@router.post("/api/courses")
def create_course(body: CourseIn, user: dict = Depends(current_user)):
    q = billing.quote(body.student_seats, body.staff_seats, body.token_cap, body.cap_period)  # validates the plan
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO courses(name,owner_id,status,student_seats,staff_seats,token_cap,cap_period,token_ceiling,"
            "price_cents,student_code,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?) RETURNING id",
            (body.name.strip(), user["id"], "pending", body.student_seats, body.staff_seats, body.token_cap,
             body.cap_period, q["token_ceiling"], q["price_cents"], new_student_code(), now()))
        course_id = cur.fetchone()["id"]
        conn.execute("INSERT INTO memberships(course_id,user_id,role,status,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                     (course_id, user["id"], "owner", "active", now(), now()))
    return {"id": course_id, "status": "pending", "price_cents": q["price_cents"]}


class CourseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    email_domain: str | None = Field(default=None, max_length=100)
    code_expires_at: float | None = None
    token_cap: int | None = None
    cap_period: str | None = None


@router.patch("/api/courses/{course_id}")
def update_course(body: CourseUpdate, m: Member = Depends(get_staff)):
    sets: dict = {}
    given = body.model_fields_set
    if body.name is not None:
        sets["name"] = body.name.strip()
    if "email_domain" in given:
        domain = (body.email_domain or "").strip().lower().lstrip("@")
        if domain and not DOMAIN_RE.match(domain):
            raise HTTPException(422, "Enter a domain like ucla.edu, or leave it empty.")
        sets["email_domain"] = domain or None
    if "code_expires_at" in given:
        if body.code_expires_at is not None and body.code_expires_at <= now():
            raise HTTPException(422, "The expiry date must be in the future.")
        sets["code_expires_at"] = body.code_expires_at
    if body.token_cap is not None or body.cap_period is not None:
        cap = body.token_cap if body.token_cap is not None else m.course["token_cap"]
        period = body.cap_period or m.course["cap_period"]
        billing.validate_cap(cap, period)
        sets.update({"token_cap": cap, "cap_period": period})
    if sets:
        with db() as conn:
            conn.execute(f"UPDATE courses SET {', '.join(f'{k}=?' for k in sets)} WHERE id=?",
                         (*sets.values(), m.course["id"]))
    return {"ok": True}


@router.post("/api/courses/{course_id}/code/rotate")
def rotate_code(m: Member = Depends(get_staff)):
    code = new_student_code()
    with db() as conn:
        conn.execute("UPDATE courses SET student_code=? WHERE id=?", (code, m.course["id"]))
    return {"student_code": code}


class SetupIn(BaseModel):
    step: str
    done: bool = True


def mark_setup(conn, course_id: int, step: str, done: bool = True) -> None:
    row = conn.execute("SELECT setup FROM courses WHERE id=?", (course_id,)).fetchone()
    setup = json.loads(row["setup"] or "{}")
    setup[step] = done
    conn.execute("UPDATE courses SET setup=? WHERE id=?", (json.dumps(setup), course_id))


@router.post("/api/courses/{course_id}/setup")
def setup_step(body: SetupIn, m: Member = Depends(get_staff)):
    if body.step not in SETUP_STEPS:
        raise HTTPException(422, "Unknown setup step")
    with db() as conn:
        mark_setup(conn, m.course["id"], body.step, body.done)
    return {"ok": True}


# ---- joining ----------------------------------------------------------------------------------------
class JoinIn(BaseModel):
    code: str = Field(min_length=4, max_length=40)


def _email_allowed(email: str, domain: str | None) -> bool:
    if not domain:
        return True
    host = email.rsplit("@", 1)[-1].lower()
    return host == domain or host.endswith("." + domain)


def _set_membership(conn, course_id: int, user_id: int, role: str) -> None:
    conn.execute("INSERT INTO memberships(course_id,user_id,role,status,created_at,updated_at) VALUES(?,?,?,?,?,?) "
                 "ON CONFLICT(course_id, user_id) DO UPDATE SET role=excluded.role, status='active', "
                 "updated_at=excluded.updated_at", (course_id, user_id, role, "active", now(), now()))


def _join_staff(conn, code: str, user: dict) -> dict:
    row = conn.execute("SELECT * FROM staff_codes WHERE code_hash=?", (hash_code(code),)).fetchone()
    if not row or row["revoked_at"] or row["used_by"]:
        raise HTTPException(404, "That staff code isn't valid. Ask the course owner for a new one.")
    if row["expires_at"] <= now():
        raise HTTPException(410, "That staff code has expired. Ask the course owner for a new one.")
    existing = conn.execute("SELECT role, status FROM memberships WHERE course_id=? AND user_id=?",
                            (row["course_id"], user["id"])).fetchone()
    if existing and existing["status"] == "blocked":
        raise HTTPException(403, "You can't join this course. Contact the course owner.")
    if existing and existing["status"] == "active" and existing["role"] in ("owner", "staff"):
        return {"course_id": row["course_id"], "role": existing["role"], "already": True}
    claimed = conn.execute("UPDATE staff_codes SET used_by=?, used_at=? WHERE id=? AND used_by IS NULL "
                           "AND revoked_at IS NULL AND expires_at>? RETURNING id",
                           (user["id"], now(), row["id"], now())).fetchone()
    if not claimed:
        raise HTTPException(404, "That staff code isn't valid. Ask the course owner for a new one.")
    _set_membership(conn, row["course_id"], user["id"], "staff")
    return {"course_id": row["course_id"], "role": "staff"}


@router.post("/api/join")
def join(body: JoinIn, user: dict = Depends(current_user)):
    code = normalize_code(body.code)
    with db() as conn:
        if code.startswith("STAFF-"):
            return _join_staff(conn, code, user)
        c = conn.execute("SELECT * FROM courses WHERE student_code=?", (code,)).fetchone()
        if not c:
            raise HTTPException(404, "That code doesn't match a course. Check it with your instructor.")
        if c["status"] != "active":
            raise HTTPException(409, "This course isn't open yet. Try again once your instructor has finished setting it up.")
        if c["code_expires_at"] and c["code_expires_at"] <= now():
            raise HTTPException(410, "This course code has expired. Ask your instructor for the current one.")
        existing = conn.execute("SELECT role, status FROM memberships WHERE course_id=? AND user_id=?",
                                (c["id"], user["id"])).fetchone()
        if existing and existing["status"] == "active":
            return {"course_id": c["id"], "role": existing["role"], "already": True}
        if existing and existing["status"] == "blocked":
            raise HTTPException(403, "You can't rejoin this course. Contact your instructor.")
        if not _email_allowed(user["email"], c["email_domain"]):
            raise HTTPException(403, f"This course only accepts @{c['email_domain']} email addresses. "
                                     "Sign up with your school email to join.")
        lock_row(conn, "courses", c["id"])  # two students joining at once can't both take the last seat
        used = conn.execute("SELECT COUNT(*) AS n FROM memberships WHERE course_id=? AND role='student' "
                            "AND status='active'", (c["id"],)).fetchone()["n"]
        if used >= c["student_seats"]:
            raise HTTPException(409, "This course is full. Ask your instructor to add seats.")
        _set_membership(conn, c["id"], user["id"], "student")
    return {"course_id": c["id"], "role": "student"}


# ---- guidelines -------------------------------------------------------------------------------------
class TaggedGuideline(BaseModel):
    text: str = Field(min_length=1)
    doc_ids: list[str] = Field(min_length=1)


class GuidelinesIn(BaseModel):
    general: str = ""
    tagged: list[TaggedGuideline] = []


def load_guidelines(conn, course_id: int) -> dict:
    general = conn.execute("SELECT general_guideline FROM courses WHERE id=?", (course_id,)).fetchone()
    rows = conn.execute("SELECT id, text, doc_ids FROM guidelines WHERE course_id=? ORDER BY id", (course_id,)).fetchall()
    valid = {r["id"] for r in conn.execute("SELECT id FROM documents WHERE course_id=?", (course_id,)).fetchall()}
    return {"general": general["general_guideline"] if general else "",
            "tagged": [{"id": r["id"], "text": r["text"], "doc_ids": [d for d in json.loads(r["doc_ids"]) if d in valid]}
                       for r in rows]}


@router.get("/api/courses/{course_id}/guidelines")
def get_guidelines(m: Member = Depends(get_staff)):
    with db() as conn:
        out = load_guidelines(conn, m.course["id"])
    return {**out, "limits": {"general": config.GUIDELINE_MAX_CHARS, "tagged": config.TAGGED_GUIDELINE_MAX_CHARS,
                              "count": config.MAX_TAGGED_GUIDELINES}}


@router.put("/api/courses/{course_id}/guidelines")
def put_guidelines(body: GuidelinesIn, m: Member = Depends(get_staff)):
    general = body.general.strip()
    if len(general) > config.GUIDELINE_MAX_CHARS:
        raise HTTPException(422, f"The general guideline can be at most {config.GUIDELINE_MAX_CHARS} characters.")
    if len(body.tagged) > config.MAX_TAGGED_GUIDELINES:
        raise HTTPException(422, f"At most {config.MAX_TAGGED_GUIDELINES} additional guidelines.")
    with db() as conn:
        valid = {r["id"] for r in conn.execute("SELECT id FROM documents WHERE course_id=?", (m.course["id"],)).fetchall()}
        for g in body.tagged:
            if len(g.text.strip()) > config.TAGGED_GUIDELINE_MAX_CHARS:
                raise HTTPException(422, f"Each additional guideline can be at most {config.TAGGED_GUIDELINE_MAX_CHARS} characters.")
            g.doc_ids = [d for d in g.doc_ids if d in valid]  # drop materials that were deleted meanwhile
            if not g.doc_ids:
                raise HTTPException(422, "Each additional guideline needs at least one material from this course.")
        conn.execute("UPDATE courses SET general_guideline=? WHERE id=?", (general, m.course["id"]))
        conn.execute("DELETE FROM guidelines WHERE course_id=?", (m.course["id"],))
        for g in body.tagged:
            conn.execute("INSERT INTO guidelines(course_id,text,doc_ids,created_at,updated_at) VALUES(?,?,?,?,?)",
                         (m.course["id"], g.text.strip(), json.dumps(sorted(set(g.doc_ids))), now(), now()))
        mark_setup(conn, m.course["id"], "guidelines")
    return {"ok": True}


# ---- pause windows -----------------------------------------------------------------------------------
class PauseIn(BaseModel):
    starts_at: float
    ends_at: float
    message: str = Field(default="", max_length=300)


@router.get("/api/courses/{course_id}/pauses")
def list_pauses(m: Member = Depends(get_staff)):
    with db() as conn:
        rows = conn.execute("SELECT id, starts_at, ends_at, message FROM pauses WHERE course_id=? AND ends_at>? "
                            "ORDER BY starts_at", (m.course["id"], now() - 7 * 86400)).fetchall()
    t = now()
    return [{**dict(r), "state": "active" if r["starts_at"] <= t < r["ends_at"] else
             ("past" if r["ends_at"] <= t else "scheduled")} for r in rows]


@router.post("/api/courses/{course_id}/pauses")
def add_pause(body: PauseIn, m: Member = Depends(get_staff)):
    if body.ends_at <= body.starts_at:
        raise HTTPException(422, "The pause must end after it starts.")
    if body.ends_at <= now():
        raise HTTPException(422, "The pause must end in the future.")
    if body.ends_at - body.starts_at > 14 * 86400:
        raise HTTPException(422, "A pause can last at most 14 days.")
    with db() as conn:
        cur = conn.execute("INSERT INTO pauses(course_id,starts_at,ends_at,message,created_at) VALUES(?,?,?,?,?) RETURNING id",
                           (m.course["id"], body.starts_at, body.ends_at, body.message.strip(), now()))
        return {"id": cur.fetchone()["id"]}


@router.delete("/api/courses/{course_id}/pauses/{pause_id}")
def delete_pause(pause_id: int, m: Member = Depends(get_staff)):
    with db() as conn:
        conn.execute("DELETE FROM pauses WHERE id=? AND course_id=?", (pause_id, m.course["id"]))
    return {"ok": True}
