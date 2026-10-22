"""Sign-up and login: local accounts (development) and Supabase access tokens (production)."""
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app import auth, config
from conftest import create_course, email, join, new_user, q1

SUPA = "https://proj.supabase.co"


def test_signup_login_and_me(app):
    c = TestClient(app)
    ada = email("ada")
    r = c.post("/api/auth/signup", json={"email": ada.replace("ada", "Ada"), "password": "password123", "name": "Ada"})
    assert r.status_code == 200
    assert r.json()["user"]["email"] == ada
    assert c.post("/api/auth/signup", json={"email": ada, "password": "password123", "name": "Ada"}).status_code == 409
    assert c.post("/api/auth/login", json={"email": ada, "password": "nope-nope"}).status_code == 401
    r = c.post("/api/auth/login", json={"email": ada.upper(), "password": "password123"})
    assert r.status_code == 200
    me = c.get("/api/me", headers={"Authorization": f"Bearer {r.json()['token']}"}).json()
    assert me["name"] == "Ada" and me["courses"] == []


def test_signup_validation(app):
    c = TestClient(app)
    assert c.post("/api/auth/signup", json={"email": "x@y.edu", "password": "short", "name": "X"}).status_code == 422
    assert c.post("/api/auth/signup", json={"email": "not-an-email", "password": "password123",
                                            "name": "X"}).status_code == 422


def test_requires_sign_in(app):
    c = TestClient(app)
    assert c.get("/api/me").status_code == 401
    assert c.post("/api/courses", json={}).status_code in (401, 422)
    assert c.get("/api/me", headers={"Authorization": "Bearer u.1.9999999999.deadbeef"}).status_code == 401


def test_tampered_and_expired_tokens(app, monkeypatch):
    good = new_user(app)
    token = good.headers["Authorization"].split(" ")[1]
    uid = token.split(".")[1]
    forged = token.replace(f"u.{uid}.", f"u.{int(uid) + 1}.", 1)
    assert TestClient(app).get("/api/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    monkeypatch.setattr(config, "TOKEN_TTL_SECONDS", -10)
    stale = auth.make_session_token(int(uid))
    assert TestClient(app).get("/api/me", headers={"Authorization": f"Bearer {stale}"}).status_code == 401


def test_me_lists_memberships(app):
    owner = new_user(app)
    cid = create_course(owner, name="Me Course")
    me = owner.get("/api/me").json()
    assert {"id": cid, "name": "Me Course", "status": "active", "role": "owner"} in me["courses"]


def test_password_hashing():
    h = auth.hash_password("correct horse")
    assert h.startswith("scrypt$") and auth.check_password("correct horse", h)
    assert not auth.check_password("wrong", h) and not auth.check_password("x", None)


# ---- Supabase access tokens ------------------------------------------------------------------
class _FakeJWKS:
    def __init__(self, key):
        self.key = key

    def get_signing_key_from_jwt(self, token):
        return self


@pytest.fixture
def supabase(monkeypatch):
    private = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(config, "AUTH_PROVIDER", "supabase")
    monkeypatch.setattr(config, "SUPABASE_URL", SUPA)
    monkeypatch.setattr(auth, "_jwks_client", _FakeJWKS(private.public_key()))
    return private


def _token(key, **over):
    claims = {"sub": "5c1b3f2a-0000-4000-8000-000000000001", "email": "Grace@Example.edu", "role": "authenticated",
              "aud": "authenticated", "iss": f"{SUPA}/auth/v1", "exp": int(time.time()) + 600,
              "user_metadata": {"full_name": "Grace Hopper"}}
    claims.update(over)
    return jwt.encode(claims, key, algorithm="ES256")


def test_supabase_token_creates_user(app, supabase):
    c = TestClient(app)
    r = c.get("/api/me", headers={"Authorization": f"Bearer {_token(supabase)}"})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Grace Hopper" and r.json()["email"] == "grace@example.edu"
    again = c.get("/api/me", headers={"Authorization": f"Bearer {_token(supabase)}"}).json()
    assert again["id"] == r.json()["id"]  # same Supabase user -> same row
    assert c.post("/api/auth/login", json={"email": "a@b.edu", "password": "password123"}).status_code == 404


@pytest.mark.parametrize("over", [{"aud": "anon"}, {"exp": int(time.time()) - 5}, {"iss": "https://evil.example/auth/v1"},
                                  {"role": "anon"}, {"is_anonymous": True}])
def test_supabase_rejects_bad_claims(app, supabase, over):
    r = TestClient(app).get("/api/me", headers={"Authorization": f"Bearer {_token(supabase, **over)}"})
    assert r.status_code == 401


def test_supabase_rejects_other_signing_key(app, supabase):
    other = ec.generate_private_key(ec.SECP256R1())
    assert TestClient(app).get("/api/me", headers={"Authorization": f"Bearer {_token(other)}"}).status_code == 401


def test_supabase_hs256_needs_secret(app, supabase, monkeypatch):
    claims = {"sub": "hs-user", "email": "h@s.edu", "role": "authenticated", "aud": "authenticated",
              "iss": f"{SUPA}/auth/v1", "exp": int(time.time()) + 600}
    token = jwt.encode(claims, "x" * 40, algorithm="HS256")
    assert TestClient(app).get("/api/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    monkeypatch.setattr(config, "SUPABASE_JWT_SECRET", "x" * 40)
    assert TestClient(app).get("/api/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_config_exposes_auth_provider(app, supabase, monkeypatch):
    monkeypatch.setattr(config, "SUPABASE_ANON_KEY", "public-anon-key")
    from app import main
    monkeypatch.setattr(main, "_google_enabled", lambda: True)
    cfg = TestClient(app).get("/api/config").json()
    assert cfg["auth"] == {"provider": "supabase", "supabase_url": SUPA, "supabase_anon_key": "public-anon-key",
                           "google": True}
    assert cfg["billing"]["mode"] == "mock" and "cap_presets" in cfg["plans"]


def test_student_vs_instructor_signup_and_course_creation_guard(app):
    c = TestClient(app)
    stu_email = email("student_role")
    r_stu = c.post(
        "/api/auth/signup",
        json={"email": stu_email, "password": "password123", "name": "Bruin Student", "account_type": "student"},
    )
    assert r_stu.status_code == 200, r_stu.text
    stu_token = r_stu.json()["token"]
    assert r_stu.json()["user"]["account_type"] == "student"

    me_stu = c.get("/api/me", headers={"Authorization": f"Bearer {stu_token}"}).json()
    assert me_stu["account_type"] == "student"

    # Students cannot create courses (403 Forbidden)
    r_create_blocked = c.post(
        "/api/courses",
        headers={"Authorization": f"Bearer {stu_token}"},
        json={"name": "Blocked Course", "student_seats": 30, "staff_seats": 2, "token_cap": 100_000, "cap_period": "week"},
    )
    assert r_create_blocked.status_code == 403

    # Instructors / Tutors can create courses
    inst_email = email("inst_role")
    r_inst = c.post(
        "/api/auth/signup",
        json={"email": inst_email, "password": "password123", "name": "Prof Bruin", "account_type": "instructor"},
    )
    assert r_inst.status_code == 200, r_inst.text
    inst_token = r_inst.json()["token"]
    assert r_inst.json()["user"]["account_type"] == "instructor"
    r_create_ok = c.post(
        "/api/courses",
        headers={"Authorization": f"Bearer {inst_token}"},
        json={"name": "Allowed Course", "student_seats": 30, "staff_seats": 2, "token_cap": 100_000, "cap_period": "week"},
    )
    assert r_create_ok.status_code == 200, r_create_ok.text


def test_google_account_takes_role_chosen_before_sign_in(app, supabase):
    c = TestClient(app)
    c.headers["Authorization"] = f"Bearer {_token(supabase, sub='5c1b3f2a-0000-4000-8000-0000000000aa')}"
    assert c.get("/api/me").json()["account_type"] == "student"  # Google sends no role: a student by default
    assert c.put("/api/me/account-type", json={"account_type": "admin"}).status_code == 422
    r = c.put("/api/me/account-type", json={"account_type": "instructor"})
    assert r.status_code == 200, r.text
    assert r.json()["account_type"] == "instructor" and r.json()["courses"] == []
    assert c.get("/api/me").json()["account_type"] == "instructor"
    create_course(c)
    # Once the account belongs to a course its type is settled.
    assert c.put("/api/me/account-type", json={"account_type": "student"}).status_code == 409


def test_course_member_cannot_change_account_type(app):
    owner = new_user(app, "Owner")
    course = create_course(owner)
    stu = new_user(app, "Stu")
    join(stu, q1("SELECT student_code FROM courses WHERE id=?", course)["student_code"])
    assert stu.put("/api/me/account-type", json={"account_type": "instructor"}).status_code == 409
    assert stu.get("/api/me").json()["account_type"] == "student"


_auto = iter(range(10_000))


def _signup(app, account_type: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/auth/signup", json={"email": email(f"auto{next(_auto)}_{account_type}"), "password": "password123",
                                         "name": "Auto", "account_type": account_type})
    assert r.status_code == 200, r.text
    c.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return c


def test_new_students_join_the_default_course(app, monkeypatch):
    owner = new_user(app, "Owner")
    cid = create_course(owner)
    monkeypatch.setattr(config, "DEFAULT_COURSE_ID", cid)

    stu = _signup(app, "student")
    assert [(x["id"], x["role"]) for x in stu.get("/api/me").json()["courses"]] == [(cid, "student")]
    assert [(x["id"], x["role"]) for x in _signup(app, "instructor").get("/api/me").json()["courses"]] == []

    # A removed student isn't put back on their next sign-in.
    assert owner.post(f"/api/courses/{cid}/members/{stu.get('/api/me').json()['id']}",
                      json={"action": "remove"}).status_code == 200
    assert stu.get("/api/me").json()["courses"] == []


def test_default_course_respects_seats_and_status(app, monkeypatch):
    owner = new_user(app, "Owner")
    cid = create_course(owner, student_seats=1)
    monkeypatch.setattr(config, "DEFAULT_COURSE_ID", cid)
    assert len(_signup(app, "student").get("/api/me").json()["courses"]) == 1
    assert _signup(app, "student").get("/api/me").json()["courses"] == []  # full: they can still use a code

    pending = create_course(owner, activate=False)
    monkeypatch.setattr(config, "DEFAULT_COURSE_ID", pending)
    assert _signup(app, "student").get("/api/me").json()["courses"] == []


def test_google_instructor_is_not_enrolled_in_the_default_course(app, supabase, monkeypatch):
    owner = TestClient(app)
    owner.headers["Authorization"] = f"Bearer {_token(supabase, sub='5c1b3f2a-0000-4000-8000-0000000000ba')}"
    assert owner.put("/api/me/account-type", json={"account_type": "instructor"}).status_code == 200
    monkeypatch.setattr(config, "DEFAULT_COURSE_ID", create_course(owner))
    c = TestClient(app)
    c.headers["Authorization"] = f"Bearer {_token(supabase, sub='5c1b3f2a-0000-4000-8000-0000000000bb')}"
    # The app sends the role picked before the Google redirect first, so no student enrollment happens.
    r = c.put("/api/me/account-type", json={"account_type": "instructor"})
    assert r.status_code == 200 and r.json()["courses"] == []
