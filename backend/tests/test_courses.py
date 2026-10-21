"""Creating and paying for courses, joining with codes, staff codes, roles and the roster (PRD §2)."""
import hashlib
import hmac
import json
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import billing, config
from conftest import create_course, email, execute, join, new_user, pay, q1


def test_quote_formula_and_validation(app):
    owner = new_user(app)
    q = owner.post("/api/billing/quote", json={"student_seats": 40, "staff_seats": 2, "token_cap": 100_000,
                                               "cap_period": "week"}).json()
    assert q["price_cents"] == 11_700  # $19 base + 2 x $9 + 40 x $2 (TECHNICAL.md §5)
    assert q["token_ceiling"] == 43 * 100_000 * 10 and q["approx_questions"] == 25
    assert billing.quote(40, 2, 10_000, "day")["seat_cents"] == 140  # a daily cap counts 7x per week
    for bad in ({"student_seats": 0}, {"staff_seats": -1}, {"token_cap": 10}, {"cap_period": "month"}):
        body = {"student_seats": 10, "staff_seats": 0, "token_cap": 100_000, "cap_period": "week", **bad}
        assert owner.post("/api/billing/quote", json=body).status_code == 422


def test_course_is_pending_until_paid(app):
    owner = new_user(app, "Prof")
    cid = create_course(owner, activate=False)
    view = owner.get(f"/api/courses/{cid}").json()
    assert view["status"] == "pending" and view["role"] == "owner" and not view["open"]
    student = new_user(app)
    assert student.post("/api/join", json={"code": view["student_code"]}).status_code == 409
    assert student.post(f"/api/courses/{cid}/checkout", json={}).status_code == 404  # only the owner can pay
    pay(owner, cid)
    assert owner.get(f"/api/courses/{cid}").json()["status"] == "active"
    assert owner.post(f"/api/courses/{cid}/checkout", json={}).status_code == 409  # already paid


def test_test_checkout_link_is_signed(app):
    owner = new_user(app)
    cid = create_course(owner, activate=False)
    assert TestClient(app).post(f"/api/billing/test-checkout/{cid}/pay?t=1.bad").status_code == 403
    assert q1("SELECT status FROM courses WHERE id=?", cid)["status"] == "pending"


# ---- Stripe ----------------------------------------------------------------------------------------
class _FakeSessions:
    def __init__(self):
        self.created = []

    def create(self, params):
        self.created.append(params)
        return SimpleNamespace(id="cs_test_123", url="https://checkout.stripe.test/c/cs_test_123")

    def retrieve(self, session_id):
        course = self.created[-1]["metadata"]["course_id"]
        return SimpleNamespace(to_dict=lambda: {"id": session_id, "payment_status": "paid",
                                                "metadata": {"course_id": course}})


@pytest.fixture
def stripe_mode(monkeypatch):
    sessions = _FakeSessions()
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test_dummy")
    monkeypatch.setattr(config, "STRIPE_WEBHOOK_SECRET", "whsec_dummy")
    monkeypatch.setattr(billing, "_stripe", lambda: SimpleNamespace(
        v1=SimpleNamespace(checkout=SimpleNamespace(sessions=sessions))))
    return sessions


def _webhook(client, event: dict, secret: str = "whsec_dummy"):
    payload = json.dumps(event)
    t = int(time.time())
    sig = hmac.new(secret.encode(), f"{t}.{payload}".encode(), hashlib.sha256).hexdigest()
    return client.post("/api/stripe/webhook", content=payload,
                       headers={"stripe-signature": f"t={t},v1={sig}", "content-type": "application/json"})


def test_stripe_checkout_and_webhook(app, stripe_mode):
    owner = new_user(app)
    cid = create_course(owner, activate=False)
    r = owner.post(f"/api/courses/{cid}/checkout", json={"return_url": "http://localhost:5173"})
    assert r.json() == {"url": "https://checkout.stripe.test/c/cs_test_123", "mode": "stripe"}
    params = stripe_mode.created[-1]
    assert params["metadata"] == {"course_id": str(cid)} and params["line_items"][0]["price_data"]["unit_amount"] > 0
    assert params["success_url"].startswith("http://localhost:5173/?checkout=success")
    assert "{CHECKOUT_SESSION_ID}" in params["success_url"]

    anon = TestClient(app)
    unpaid = {"id": f"evt_unpaid_{cid}", "type": "checkout.session.completed",
              "data": {"object": {"id": "cs_test_123", "payment_status": "unpaid", "metadata": {"course_id": str(cid)}}}}
    assert _webhook(anon, unpaid).status_code == 200
    assert q1("SELECT status FROM courses WHERE id=?", cid)["status"] == "pending"
    assert _webhook(anon, {**unpaid, "id": "evt_forged"}, secret="whsec_wrong").status_code == 400

    paid = {"id": f"evt_paid_{cid}", "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_test_123", "payment_status": "paid", "metadata": {"course_id": str(cid)}}}}
    assert _webhook(anon, paid).json() == {"received": True}
    assert q1("SELECT status FROM courses WHERE id=?", cid)["status"] == "active"
    assert _webhook(anon, paid).json()["duplicate"] is True


def test_stripe_return_confirms_with_stripe(app, stripe_mode):
    owner = new_user(app)
    cid = create_course(owner, activate=False)
    owner.post(f"/api/courses/{cid}/checkout", json={})
    assert owner.post(f"/api/courses/{cid}/checkout/confirm", json={"session_id": "not-a-session"}).json()["status"] == "pending"
    assert owner.post(f"/api/courses/{cid}/checkout/confirm", json={"session_id": "cs_test_123"}).json()["status"] == "active"


def test_test_checkout_disabled_with_stripe_or_in_production(app, stripe_mode, monkeypatch):
    owner = new_user(app)
    cid = create_course(owner, activate=False)
    assert TestClient(app).get(f"/api/billing/test-checkout/{cid}?t=x").status_code == 404
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "")
    monkeypatch.setattr(config, "PRODUCTION", True)
    assert TestClient(app).get(f"/api/billing/test-checkout/{cid}?t=x").status_code == 404
    assert owner.post(f"/api/courses/{cid}/checkout", json={}).status_code == 503


# ---- joining --------------------------------------------------------------------------------------
def test_join_with_code(app):
    owner = new_user(app)
    cid = create_course(owner)
    code = owner.get(f"/api/courses/{cid}").json()["student_code"]
    s = new_user(app)
    assert s.post("/api/join", json={"code": "ZZZZ-ZZZZ"}).status_code == 404
    assert join(s, code.lower().replace("-", " ")) == {"course_id": cid, "role": "student"}  # forgiving input
    assert join(s, code)["already"] is True
    view = s.get(f"/api/courses/{cid}").json()
    assert view["role"] == "student" and "student_code" not in view and view["allowance"]["cap"] == 100_000


def test_code_rotation_and_expiry(app):
    owner = new_user(app)
    cid = create_course(owner)
    old = owner.get(f"/api/courses/{cid}").json()["student_code"]
    early = new_user(app)
    join(early, old)
    new = owner.post(f"/api/courses/{cid}/code/rotate").json()["student_code"]
    assert new != old
    assert new_user(app).post("/api/join", json={"code": old}).status_code == 404
    assert early.get(f"/api/courses/{cid}").status_code == 200  # existing members keep access
    execute("UPDATE courses SET code_expires_at=? WHERE id=?", time.time() - 1, cid)
    assert new_user(app).post("/api/join", json={"code": new}).status_code == 410


def test_email_domain_restriction(app):
    owner = new_user(app)
    cid = create_course(owner)
    assert owner.patch(f"/api/courses/{cid}", json={"email_domain": "not a domain"}).status_code == 422
    assert owner.patch(f"/api/courses/{cid}", json={"email_domain": "@UCLA.edu"}).status_code == 200
    code = owner.get(f"/api/courses/{cid}").json()["student_code"]
    r = new_user(app, email=email("someone", "gmail.com")).post("/api/join", json={"code": code})
    assert r.status_code == 403 and "ucla.edu" in r.json()["detail"]
    join(new_user(app, email=email("bruin", "ucla.edu")), code)
    join(new_user(app, email=email("bruin", "g.ucla.edu")), code)  # subdomains count


def test_seat_cap_remove_and_block(app):
    owner = new_user(app)
    cid = create_course(owner, student_seats=2)
    code = owner.get(f"/api/courses/{cid}").json()["student_code"]
    a, b, c = new_user(app), new_user(app), new_user(app)
    join(a, code)
    join(b, code)
    r = c.post("/api/join", json={"code": code})
    assert r.status_code == 409 and "full" in r.json()["detail"]
    assert owner.post(f"/api/courses/{cid}/members/{a.user['id']}", json={"action": "remove"}).status_code == 200
    r = a.get(f"/api/courses/{cid}")
    assert r.status_code == 403 and "no longer have access" in r.json()["detail"]
    assert cid not in [x["id"] for x in a.get("/api/me").json()["courses"]]
    join(c, code)  # the freed seat
    assert owner.post(f"/api/courses/{cid}/members/{b.user['id']}", json={"action": "block"}).status_code == 200
    assert owner.post(f"/api/courses/{cid}/members/{c.user['id']}", json={"action": "remove"}).status_code == 200
    assert b.post("/api/join", json={"code": code}).status_code == 403  # blocked can't rejoin
    join(a, code)  # removed can rejoin while there is a seat
    roster = owner.get(f"/api/courses/{cid}/members").json()
    statuses = {p["user_id"]: p["status"] for p in roster["students"]}
    assert statuses[a.user["id"]] == "active" and statuses[b.user["id"]] == "blocked"
    assert roster["seats"]["students"] == 1


def test_staff_codes_single_use_cap_and_revoke(app):
    owner = new_user(app, "Owner")
    cid = create_course(owner, staff_seats=2)
    first = owner.post(f"/api/courses/{cid}/staff-codes").json()
    assert first["code"].startswith("STAFF-")
    listed = owner.get(f"/api/courses/{cid}/staff-codes").json()
    assert listed[0]["last4"] == first["code"][-4:] and "code" not in listed[0]
    ta = new_user(app, "TA")
    assert join(ta, first["code"]) == {"course_id": cid, "role": "staff"}
    assert new_user(app).post("/api/join", json={"code": first["code"]}).status_code == 404  # used up
    second = owner.post(f"/api/courses/{cid}/staff-codes").json()
    assert owner.post(f"/api/courses/{cid}/staff-codes").status_code == 409  # 1 staff + 1 pending = cap of 2
    assert owner.delete(f"/api/courses/{cid}/staff-codes/{second['id']}").status_code == 200
    assert new_user(app).post("/api/join", json={"code": second["code"]}).status_code == 404  # revoked
    third = owner.post(f"/api/courses/{cid}/staff-codes").json()
    execute("UPDATE staff_codes SET expires_at=? WHERE id=?", time.time() - 1, third["id"])
    assert new_user(app).post("/api/join", json={"code": third["code"]}).status_code == 410


def test_roles_and_permissions(app):
    owner = new_user(app, "Owner")
    cid = create_course(owner)
    code = owner.get(f"/api/courses/{cid}").json()["student_code"]
    ta = new_user(app, "TA")
    join(ta, owner.post(f"/api/courses/{cid}/staff-codes").json()["code"])
    student = new_user(app)
    join(student, code)
    stranger = new_user(app)
    # staff: everything except staff codes, removing staff and billing
    assert ta.get(f"/api/courses/{cid}/members").status_code == 200
    assert ta.post(f"/api/courses/{cid}/code/rotate").status_code == 200
    assert ta.post(f"/api/courses/{cid}/staff-codes").status_code == 403
    assert ta.post(f"/api/courses/{cid}/members/{owner.user['id']}", json={"action": "remove"}).status_code == 403
    assert "billing" not in ta.get(f"/api/courses/{cid}").json()
    assert "billing" in owner.get(f"/api/courses/{cid}").json()
    # students and strangers
    assert student.get(f"/api/courses/{cid}/members").status_code == 403
    assert student.get(f"/api/courses/{cid}/dashboard").status_code == 403
    assert student.patch(f"/api/courses/{cid}", json={"name": "Mine now"}).status_code == 403
    assert stranger.get(f"/api/courses/{cid}").status_code == 404
    assert stranger.get(f"/api/courses/{cid}/materials").status_code == 404
    # the owner removes the TA
    assert owner.post(f"/api/courses/{cid}/members/{ta.user['id']}", json={"action": "remove"}).status_code == 200
    assert ta.get(f"/api/courses/{cid}/members").status_code == 403


def test_settings_and_setup_steps(app):
    owner = new_user(app)
    cid = create_course(owner)
    assert owner.patch(f"/api/courses/{cid}", json={"token_cap": 50_000, "cap_period": "day"}).status_code == 200
    assert owner.patch(f"/api/courses/{cid}", json={"token_cap": 1}).status_code == 422
    assert owner.patch(f"/api/courses/{cid}", json={"code_expires_at": time.time() - 5}).status_code == 422
    view = owner.get(f"/api/courses/{cid}").json()
    assert view["plan"]["token_cap"] == 50_000 and view["plan"]["cap_period"] == "day"
    steps = {s["step"]: s["done"] for s in view["setup"]}
    assert steps == {"materials": False, "modes": False, "guidelines": False, "preview": False, "share": False}
    assert owner.post(f"/api/courses/{cid}/setup", json={"step": "share"}).status_code == 200
    assert owner.post(f"/api/courses/{cid}/setup", json={"step": "bogus"}).status_code == 422
    assert {s["step"]: s["done"] for s in owner.get(f"/api/courses/{cid}").json()["setup"]}["share"] is True
