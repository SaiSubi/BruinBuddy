"""Who is calling: Supabase Auth in production, local email + password accounts in development.

Roles are never part of the account. They come from course memberships (courses.py)."""
import re
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from . import auth, config
from .db import db, now

router = APIRouter()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


ACCOUNT_TYPES = ("student", "instructor")


def _normalize_account_type(raw: str | None) -> str:
    val = (raw or "").strip().lower()
    if val in ("instructor", "professor", "tutor", "staff", "teacher", "faculty"):
        return "instructor"
    if val == "student":
        return "student"
    return "instructor"


class SignupIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=200)
    name: str = Field(min_length=1, max_length=60)
    account_type: str = Field(default="instructor", max_length=32)


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)


def _public(row) -> dict:
    keys = row.keys() if hasattr(row, "keys") else ()
    acct = row["account_type"] if "account_type" in keys and row["account_type"] else "instructor"
    return {"id": row["id"], "email": row["email"], "name": row["name"], "account_type": acct}


def _supabase_user(claims: dict) -> dict:
    """Find or create the users row for a verified Supabase token."""
    sub = claims["sub"]
    email = (claims.get("email") or "").strip().lower()
    meta = claims.get("user_metadata") or {}
    name = str(meta.get("name") or meta.get("full_name") or email.split("@")[0] or "Student").strip()[:60]
    acct_type = _normalize_account_type(meta.get("account_type") or "student")
    with db() as conn:
        row = conn.execute("SELECT id, email, name, account_type FROM users WHERE auth_id=?", (sub,)).fetchone()
        if row:
            if email and row["email"] != email:
                conn.execute("UPDATE users SET email=? WHERE id=?", (email, row["id"]))
            return {**_public(row), "email": email or row["email"]}
        conn.execute(
            "INSERT INTO users(auth_id,email,name,account_type,created_at) VALUES(?,?,?,?,?) ON CONFLICT(auth_id) DO NOTHING",
            (sub, email, name, acct_type, now()),
        )
        row = conn.execute("SELECT id, email, name, account_type FROM users WHERE auth_id=?", (sub,)).fetchone()
    return _public(row)


def current_user(authorization: str | None = Header(default=None)) -> dict:
    token = authorization[7:].strip() if authorization and authorization.lower().startswith("bearer ") else ""
    if token and config.AUTH_PROVIDER == "supabase":
        claims = auth.verify_supabase_token(token)
        if claims:
            return _supabase_user(claims)
    elif token:
        user_id = auth.verify_session_token(token)
        if user_id:
            with db() as conn:
                row = conn.execute("SELECT id, email, name, account_type FROM users WHERE id=?", (user_id,)).fetchone()
            if row:
                return _public(row)
    raise HTTPException(401, "Your session has expired. Please log in again.")


def _local_only() -> None:
    if config.AUTH_PROVIDER != "local":
        raise HTTPException(404, "Not found")


def _clean_email(raw: str) -> str:
    email = raw.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(422, "Enter a valid email address.")
    return email


@router.post("/api/auth/signup")
def signup(body: SignupIn):
    _local_only()
    email, name = _clean_email(body.email), body.name.strip()
    if not name:
        raise HTTPException(422, "Enter your name.")
    raw_type = (body.account_type or "").strip().lower()
    if raw_type not in ("student", "instructor", "professor", "tutor", "staff", "teacher", "faculty"):
        raise HTTPException(422, "Choose whether you are signing up as a student or an instructor.")
    acct_type = _normalize_account_type(raw_type)
    with db() as conn:
        if conn.execute("SELECT 1 FROM users WHERE email=? AND auth_id LIKE 'local:%'", (email,)).fetchone():
            raise HTTPException(409, "An account with this email already exists. Log in instead.")
        cur = conn.execute(
            "INSERT INTO users(auth_id,email,name,password_hash,account_type,created_at) VALUES(?,?,?,?,?,?) RETURNING id",
            (f"local:{uuid.uuid4().hex}", email, name, auth.hash_password(body.password), acct_type, now()),
        )
        user_id = cur.fetchone()["id"]
    return {
        "token": auth.make_session_token(user_id),
        "user": {"id": user_id, "email": email, "name": name, "account_type": acct_type},
    }


@router.post("/api/auth/login")
def login(body: LoginIn):
    _local_only()
    email = body.email.strip().lower()
    with db() as conn:
        row = conn.execute(
            "SELECT id, email, name, password_hash, account_type FROM users WHERE email=? AND auth_id LIKE 'local:%'",
            (email,),
        ).fetchone()
    if not row or not auth.check_password(body.password, row["password_hash"]):
        raise HTTPException(401, "Wrong email or password.")
    return {"token": auth.make_session_token(row["id"]), "user": _public(row)}


class AccountTypeIn(BaseModel):
    account_type: str = Field(max_length=32)


@router.put("/api/me/account-type")
def set_account_type(body: AccountTypeIn, user: dict = Depends(current_user)):
    """Apply the role chosen before a Google sign-in, which can't carry it in the account's metadata.

    Only a fresh account (no course memberships) may change it; course roles still come from memberships."""
    acct_type = body.account_type.strip().lower()
    if acct_type not in ACCOUNT_TYPES:
        raise HTTPException(422, "Choose whether you are a student or an instructor.")
    with db() as conn:
        if conn.execute("SELECT 1 FROM memberships WHERE user_id=?", (user["id"],)).fetchone():
            raise HTTPException(409, "This account already belongs to a course, so its type can't change.")
        conn.execute("UPDATE users SET account_type=? WHERE id=?", (acct_type, user["id"]))
    return me({**user, "account_type": acct_type})


@router.get("/api/me")
def me(user: dict = Depends(current_user)):
    from .courses import enroll_in_default_course  # courses imports this module
    enroll_in_default_course(user)
    with db() as conn:
        rows = conn.execute(
            "SELECT c.id, c.name, c.status, m.role FROM memberships m JOIN courses c ON c.id=m.course_id "
            "WHERE m.user_id=? AND m.status='active' ORDER BY c.created_at",
            (user["id"],),
        ).fetchall()
    courses_list = [{"id": r["id"], "name": r["name"], "status": r["status"], "role": r["role"]} for r in rows]
    has_staff_course = any(c["role"] in ("owner", "staff") for c in courses_list)
    has_student_only = bool(courses_list) and not has_staff_course
    if has_staff_course:
        effective_type = "instructor"
    elif has_student_only:
        effective_type = "student"
    else:
        effective_type = user.get("account_type", "instructor")
    return {**user, "account_type": effective_type, "courses": courses_list}
