"""Plans, prices and payment: the quote formula, Stripe Checkout (test mode), the webhook, and a built-in test
checkout for development.

A course becomes active only when the server has confirmed payment with Stripe: through the signed webhook (the
source of truth), or by asking Stripe for the Checkout Session when the owner returns. The browser's redirect
alone never activates anything."""
import html
import json
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from . import auth, config
from .accounts import current_user
from .db import db, now

router = APIRouter()

# ---- pricing (build default; PRD §2.7 is open) -------------------------------------------------
TERM_WEEKS = 10
PERIOD_FACTOR = {"day": 7.0, "week": 1.0, "term": 1.0 / TERM_WEEKS}  # converts a cap to its weekly equivalent
BASE_CENTS = 1900                # per course per term
STAFF_CENTS = 900                # per staff account; the owner is free
SEAT_CENTS_PER_100K_WEEKLY = 200  # per student seat, per 100k tokens of weekly allowance
MIN_SEAT_CENTS = 50
TOKENS_PER_QUESTION = 4000       # measured ≈ 3,700 per turn (AI_STRATEGY.md §6); rounded for display
CAP_PRESETS = {"day": [10_000, 20_000, 50_000], "week": [50_000, 100_000, 200_000, 400_000],
               "term": [250_000, 500_000, 1_000_000, 2_000_000]}
LIMITS = {"student_seats": (1, 2000), "staff_seats": (0, 50), "token_cap": (5_000, 5_000_000)}


def _in(name: str, value: int) -> None:
    lo, hi = LIMITS[name]
    if not lo <= value <= hi:
        raise HTTPException(422, f"{name.replace('_', ' ').capitalize()} must be between {lo:,} and {hi:,}.")


def validate_cap(token_cap: int, cap_period: str) -> None:
    if cap_period not in PERIOD_FACTOR:
        raise HTTPException(422, "The allowance period must be day, week or term.")
    _in("token_cap", token_cap)


def quote(student_seats: int, staff_seats: int, token_cap: int, cap_period: str) -> dict:
    _in("student_seats", student_seats)
    _in("staff_seats", staff_seats)
    validate_cap(token_cap, cap_period)
    weekly = token_cap * PERIOD_FACTOR[cap_period]
    seat_cents = max(MIN_SEAT_CENTS, round(weekly / 100_000 * SEAT_CENTS_PER_100K_WEEKLY))
    lines = [{"label": "Base (one course, one term)", "cents": BASE_CENTS},
             {"label": f"{staff_seats} staff × ${STAFF_CENTS / 100:.2f}", "cents": staff_seats * STAFF_CENTS},
             {"label": f"{student_seats} student seats × ${seat_cents / 100:.2f}", "cents": student_seats * seat_cents}]
    return {"price_cents": sum(line["cents"] for line in lines), "lines": lines, "seat_cents": seat_cents,
            "token_ceiling": int((student_seats + staff_seats + 1) * weekly * TERM_WEEKS),
            "approx_questions": int(token_cap // TOKENS_PER_QUESTION), "term_weeks": TERM_WEEKS}


def plan_options() -> dict:
    return {"cap_presets": CAP_PRESETS, "limits": LIMITS, "tokens_per_question": TOKENS_PER_QUESTION,
            "term_weeks": TERM_WEEKS}


class QuoteIn(BaseModel):
    student_seats: int
    staff_seats: int
    token_cap: int
    cap_period: str = "week"


@router.post("/api/billing/quote")
def quote_route(body: QuoteIn, user: dict = Depends(current_user)):
    return quote(body.student_seats, body.staff_seats, body.token_cap, body.cap_period)


# ---- activation -------------------------------------------------------------------------------------
def activate(course_id: int, session_id: str | None = None) -> bool:
    """Mark a pending course paid. Idempotent: returns False if it was already active (or doesn't exist)."""
    with db() as conn:
        row = conn.execute("UPDATE courses SET status='active', paid_at=?, stripe_session_id=COALESCE(?, stripe_session_id) "
                           "WHERE id=? AND status='pending' RETURNING id", (now(), session_id, course_id)).fetchone()
    return row is not None


def _owner_course(course_id: int, user: dict) -> dict:
    with db() as conn:
        c = conn.execute("SELECT c.* FROM courses c JOIN memberships m ON m.course_id=c.id WHERE c.id=? AND m.user_id=? "
                         "AND m.role='owner' AND m.status='active'", (course_id, user["id"])).fetchone()
    if not c:
        raise HTTPException(404, "Course not found")
    return dict(c)


def _return_base(raw: str | None) -> str:
    base = (raw or "").strip().rstrip("/")
    allowed = set(config.ALLOWED_ORIGINS) | {config.APP_URL}
    local = base.startswith(("http://localhost:", "http://127.0.0.1:")) and not config.PRODUCTION
    return base if base in allowed or local else config.APP_URL


def _stripe():
    import stripe
    return stripe.StripeClient(config.STRIPE_SECRET_KEY)


class CheckoutIn(BaseModel):
    return_url: str = Field(default="", max_length=300)


@router.post("/api/courses/{course_id}/checkout")
def checkout(course_id: int, body: CheckoutIn, user: dict = Depends(current_user)):
    c = _owner_course(course_id, user)
    if c["status"] == "active":
        raise HTTPException(409, "This course is already paid for.")
    base = _return_base(body.return_url)
    if config.billing_mode() == "mock":
        if config.PRODUCTION:
            raise HTTPException(503, "Payments are not configured on this server.")
        t = auth.make_signed("testpay", str(course_id), 3600)
        return {"url": f"/api/billing/test-checkout/{course_id}?{urlencode({'t': t, 'return': base})}", "mode": "mock"}
    import stripe
    params = {
        "mode": "payment",
        "line_items": [{"quantity": 1, "price_data": {
            "currency": "usd", "unit_amount": c["price_cents"],
            "product_data": {"name": f"BruinBuddy course plan: {c['name']}"[:250],
                             "description": f"{c['student_seats']} student seats, {c['staff_seats']} staff, "
                                            f"{c['token_cap']:,} tokens per student per {c['cap_period']}. One term."}}}],
        "success_url": f"{base}/?checkout=success&course={course_id}&session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{base}/?checkout=cancel&course={course_id}",
        "client_reference_id": str(course_id),
        "metadata": {"course_id": str(course_id)},
    }
    if user.get("email"):
        params["customer_email"] = user["email"]
    try:
        session = _stripe().v1.checkout.sessions.create(params=params)
    except stripe.StripeError:
        raise HTTPException(502, "We couldn't reach the payment provider. Please try again in a minute.")
    with db() as conn:
        conn.execute("UPDATE courses SET stripe_session_id=? WHERE id=?", (session.id, course_id))
    return {"url": session.url, "mode": "stripe"}


class ConfirmIn(BaseModel):
    session_id: str = Field(default="", max_length=300)


@router.post("/api/courses/{course_id}/checkout/confirm")
def confirm(course_id: int, body: ConfirmIn, user: dict = Depends(current_user)):
    """Called when the owner comes back from Stripe. Asks Stripe directly, so a late webhook doesn't block them."""
    c = _owner_course(course_id, user)
    if c["status"] == "active" or config.billing_mode() != "stripe" or not body.session_id.startswith("cs_"):
        return {"status": c["status"]}
    import stripe
    try:
        s = _stripe().v1.checkout.sessions.retrieve(body.session_id).to_dict()
    except stripe.StripeError:
        return {"status": c["status"]}  # the webhook will still activate it
    if str((s.get("metadata") or {}).get("course_id")) == str(course_id) and s.get("payment_status") == "paid":
        activate(course_id, s.get("id"))
        return {"status": "active"}
    return {"status": "pending"}


@router.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    if config.billing_mode() != "stripe" or not config.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(404, "Not found")
    import stripe
    payload = await request.body()
    try:
        stripe.Webhook.construct_event(payload, request.headers.get("stripe-signature"), config.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(400, "Invalid signature")
    event = json.loads(payload)
    with db() as conn:
        fresh = conn.execute("INSERT INTO stripe_events(id,type,created_at) VALUES(?,?,?) ON CONFLICT(id) DO NOTHING "
                             "RETURNING id", (event["id"], event.get("type", ""), now())).fetchone()
    if not fresh:
        return {"received": True, "duplicate": True}
    obj = (event.get("data") or {}).get("object") or {}
    if event.get("type") in ("checkout.session.completed", "checkout.session.async_payment_succeeded") \
            and obj.get("payment_status") == "paid":
        course_id = (obj.get("metadata") or {}).get("course_id") or obj.get("client_reference_id")
        if str(course_id or "").isdigit():
            activate(int(course_id), obj.get("id"))
    return {"received": True}


# ---- test checkout (development only, no Stripe keys) -------------------------------------------
def _test_checkout_allowed(course_id: int, t: str) -> dict:
    if config.PRODUCTION or config.billing_mode() != "mock":
        raise HTTPException(404, "Not found")
    if not auth.verify_signed("testpay", str(course_id), t):
        raise HTTPException(403, "This test checkout link has expired. Start checkout again.")
    with db() as conn:
        c = conn.execute("SELECT id, name, price_cents, status FROM courses WHERE id=?", (course_id,)).fetchone()
    if not c:
        raise HTTPException(404, "Not found")
    return dict(c)


@router.get("/api/billing/test-checkout/{course_id}", response_class=HTMLResponse)
def test_checkout_page(course_id: int, t: str = "", ret: str = Query(default="", alias="return")):
    c = _test_checkout_allowed(course_id, t)
    base = _return_base(ret)
    q = html.escape(urlencode({"t": t, "return": base}))
    base = html.escape(base)
    price = f"${c['price_cents'] / 100:,.2f}"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Test checkout · BruinBuddy</title><style>
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f7f7f5;color:#1d2327;display:grid;place-items:center;min-height:100vh;margin:0;padding:16px}}
.card{{background:#fff;border:1px solid #e1e3df;border-radius:12px;padding:28px;max-width:420px;width:100%}}
.note{{background:#fff7e0;border:1px solid #f0d58a;border-radius:8px;padding:10px;font-size:.9rem}}
button,a.btn{{font:inherit;border-radius:8px;padding:.6rem 1rem;cursor:pointer;text-decoration:none;display:inline-block}}
.pay{{background:#1f6f5c;color:#fff;border:0;font-weight:600}} .cancel{{background:none;border:1px solid #e1e3df;color:#1d2327}}
</style></head><body><main class="card"><h1>Test checkout</h1>
<p class="note">Stripe isn't configured on this server, so this page stands in for Stripe Checkout. No card is charged. Add Stripe test keys to use the real sandbox checkout.</p>
<p>BruinBuddy course plan: <strong>{html.escape(c['name'])}</strong></p><p style="font-size:1.6rem;margin:.4rem 0 1.2rem"><strong>{price}</strong></p>
<form method="post" action="/api/billing/test-checkout/{course_id}/pay?{q}" style="display:inline"><button class="pay" type="submit">Pay {price} (test)</button></form>
<a class="btn cancel" href="{base}/?checkout=cancel&course={course_id}">Cancel</a></main></body></html>"""


@router.post("/api/billing/test-checkout/{course_id}/pay")
def test_checkout_pay(course_id: int, t: str = "", ret: str = Query(default="", alias="return")):
    _test_checkout_allowed(course_id, t)
    activate(course_id, "test_checkout")
    return RedirectResponse(f"{_return_base(ret)}/?checkout=success&course={course_id}&session_id=test", status_code=303)
