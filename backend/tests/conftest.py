"""Tests run on a fresh temporary database with small synthetic courses, the mock LLM, the built-in test checkout
and local accounts, so they need no keys and no course export (they run in CI).

Set TEST_DATABASE_URL to run the same suite against a throw-away Postgres database."""
import itertools
import json
import os
import tempfile
import uuid
from pathlib import Path

_tmp = Path(tempfile.mkdtemp())
if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
else:
    os.environ["BB_DB_PATH"] = str(_tmp / "test.db")
    os.environ["DATABASE_URL"] = ""
os.environ.update({"BB_MOCK_LLM": "1", "BB_SYNC_JOBS": "1", "AUTH_PROVIDER": "local", "ENV": "",
                   "BB_UPLOAD_DIR": str(_tmp / "uploads"), "STRIPE_SECRET_KEY": "", "STRIPE_WEBHOOK_SECRET": "",
                   "SUPABASE_URL": "", "SUPABASE_SERVICE_KEY": "", "SUPABASE_ANON_KEY": "", "TUTOR_FALLBACK_MODEL": "",
                   "LANGFUSE_PUBLIC_KEY": "", "LANGFUSE_SECRET_KEY": ""})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

_n = itertools.count(1)
RUN = uuid.uuid4().hex[:6]  # a Postgres test database isn't reset between runs, so emails must be unique per run


def email(local: str, domain: str = "example.edu") -> str:
    return f"{local}.{RUN}@{domain}"

NOTES = """Lecture 3: Conditional probability and Bayes theorem.

Conditional probability of A given B is the probability of A and B divided by the probability of B.
Bayes theorem inverts conditional probabilities: the posterior is proportional to likelihood times prior.
The prior encodes what we believe before seeing the data, which is why Bayes theorem needs a prior.

The law of total probability splits an event across a partition of the sample space into disjoint pieces."""

READING = """# Reading: expectation and variance

The expected value of a discrete random variable is the probability weighted average of its values.
Variance measures spread: the expected squared deviation from the mean. Standard deviation is its square root.
For a binomial random variable with parameters n and p the variance equals n times p times one minus p."""

PSET1 = """Problem Set 1

Problem 1. A fair coin is tossed three times in a row. Compute the probability of observing exactly two heads
among the three tosses, and explain your counting carefully using the sample space of sequences.

Problem 2. A diagnostic screening test for a rare disease is positive for ninety five percent of sick patients.
Use Bayes theorem to find the probability that a patient with a positive screening result is actually sick."""

SOL1 = """Problem Set 1 Solutions

Solution 1. The probability of exactly two heads equals three eighths because the three favorable sequences
HHT HTH THH appear among eight equally likely outcomes enumerated in the sample space listing.

Solution 2. Applying Bayes rule the posterior chance of sickness given positivity works out to roughly
sixteen percent once the tiny base rate multiplies the sensitivity in the numerator calculation."""

PSET2 = """Problem Set 2

Problem 1. Let X be the number rolled on a fair six sided die. Compute the expected value of X and the variance
of X using the definition of expectation for a discrete random variable with equally likely outcomes."""

SOL2 = """Problem Set 2 Solutions

Solution 1. The expected roll equals three and a half since the six faces average to seven halves, and the variance
equals thirty five twelfths after subtracting the squared mean from the average of the squared faces."""


@pytest.fixture(scope="session")
def app():
    from app.main import app as fastapi_app
    with TestClient(fastapi_app):  # runs startup: schema creation
        yield fastapi_app


@pytest.fixture(autouse=True)
def _clear_mock_calls():
    from app import llm
    llm.MOCK_CALLS.clear()
    yield


def new_user(app, name: str = "Test User", email: str | None = None) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/auth/signup", json={"email": email or f"user{next(_n)}.{RUN}@example.edu", "password": "password123", "name": name})
    assert r.status_code == 200, r.text
    c.headers["Authorization"] = f"Bearer {r.json()['token']}"
    c.user = r.json()["user"]
    return c


def pay(owner: TestClient, cid: int) -> None:
    r = owner.post(f"/api/courses/{cid}/checkout", json={"return_url": "http://localhost:5173"})
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    assert owner.get(url).status_code == 200  # the test checkout page renders
    r = owner.post(url.replace(f"/test-checkout/{cid}?", f"/test-checkout/{cid}/pay?"), follow_redirects=False)
    assert r.status_code == 303 and "checkout=success" in r.headers["location"]


def create_course(owner: TestClient, *, name: str = "Stats 100", student_seats: int = 30, staff_seats: int = 2,
                  token_cap: int = 100_000, cap_period: str = "week", activate: bool = True) -> int:
    r = owner.post("/api/courses", json={"name": name, "student_seats": student_seats, "staff_seats": staff_seats,
                                         "token_cap": token_cap, "cap_period": cap_period})
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    if activate:
        pay(owner, cid)
    return cid


def upload(owner: TestClient, cid: int, kind: str, files: dict, pset_ids: list | None = None, rights: bool = True):
    r = owner.post(f"/api/courses/{cid}/materials",
                   data={"kind": kind, "rights": "true" if rights else "false", "pset_ids": json.dumps(pset_ids or [])},
                   files=[("files", (name, content if isinstance(content, bytes) else content.encode(), "text/plain"))
                          for name, content in files.items()])
    return r


def upload_ok(owner: TestClient, cid: int, kind: str, files: dict, pset_ids: list | None = None) -> list[str]:
    r = upload(owner, cid, kind, files, pset_ids)
    assert r.status_code == 200, r.text
    return [d["id"] for d in r.json()["created"]]


def setup_course(owner: TestClient, **kw) -> dict:
    """An active course with notes, a reading, two problem sets and their linked solutions."""
    cid = create_course(owner, **kw)
    notes = upload_ok(owner, cid, "lecture_notes", {"Lecture 3 - Bayes.txt": NOTES})[0]
    reading = upload_ok(owner, cid, "reading", {"Reading - Variance.md": READING})[0]
    p1 = upload_ok(owner, cid, "problem_set", {"Problem Set 1.txt": PSET1})[0]
    p2 = upload_ok(owner, cid, "problem_set", {"Problem Set 2.txt": PSET2})[0]
    s1 = upload_ok(owner, cid, "solution", {"Problem Set 1 Solutions.txt": SOL1}, [p1])[0]
    s2 = upload_ok(owner, cid, "solution", {"Problem Set 2 Solutions.txt": SOL2}, [p2])[0]
    code = owner.get(f"/api/courses/{cid}").json()["student_code"]
    return {"id": cid, "notes": notes, "reading": reading, "p1": p1, "p2": p2, "s1": s1, "s2": s2, "code": code}


def join(client: TestClient, code: str) -> dict:
    r = client.post("/api/join", json={"code": code})
    assert r.status_code == 200, r.text
    return r.json()


def student_in(app, course: dict, name: str = "Student") -> TestClient:
    s = new_user(app, name)
    join(s, course["code"])
    return s


def new_chat(client: TestClient, cid: int, kind: str = "chat", doc_id: str | None = None) -> int:
    r = client.post(f"/api/courses/{cid}/chats", json={"kind": kind, "doc_id": doc_id})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def ask(client: TestClient, chat_id: int, text: str) -> list[dict]:
    r = client.post(f"/api/chats/{chat_id}/messages", json={"content": text})
    assert r.status_code == 200, r.text
    return [json.loads(line[6:]) for line in r.text.splitlines() if line.startswith("data: ")]


def q1(sql: str, *params):
    from app.db import db
    with db() as conn:
        return conn.execute(sql, params).fetchone()


def execute(sql: str, *params) -> None:
    from app.db import db
    with db() as conn:
        conn.execute(sql, params)


def tutor_prompts() -> list[str]:
    from app import llm
    return [c["messages"][0]["content"] for c in llm.MOCK_CALLS if c["purpose"] == "tutor"]
