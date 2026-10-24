"""Langfuse tracing (tracing.py) against a fake client: one trace per answer, solution text never sent, and a
broken tracer never breaks a reply."""
import json
from contextlib import contextmanager

import pytest

from app import tracing
from app.tutor import SAFE_REPLY
from conftest import SOL1, ask, new_chat, new_user, setup_course, student_in

SOLUTION_PHRASE = "three favorable sequences"


class FakeObs:
    def __init__(self, lf, kind, name, trace_id, **kw):
        self.lf, self.kind, self.name, self.trace_id, self.id = lf, kind, name, trace_id, f"obs{len(lf.obs)}"
        self.fields, self.trace, self.ended = dict(kw), dict(lf.propagated), False

    def update(self, **kw):
        self.fields.update(kw)

    def create_event(self, *, name, **kw):
        return self.lf._new("event", name, trace_context={"trace_id": self.trace_id, "parent_span_id": self.id}, **kw)

    def end(self):
        self.ended = True


class FakeLangfuse:
    def __init__(self):
        self.obs: list[FakeObs] = []
        self.propagated: dict = {}

    def _new(self, kind, name, trace_context=None, **kw):
        tid = (trace_context or {}).get("trace_id") or f"t{len(self.obs)}"
        o = FakeObs(self, kind, name, tid, parent=(trace_context or {}).get("parent_span_id"), **kw)
        self.obs.append(o)
        return o

    def start_observation(self, *, name, as_type="span", **kw):
        return self._new(as_type, name, **kw)

    def flush(self):
        pass


@pytest.fixture
def lf(monkeypatch):
    fake = FakeLangfuse()

    @contextmanager
    def propagate(**fields):  # langfuse.propagate_attributes: trace fields for observations created inside
        fake.propagated = {k: v for k, v in fields.items() if v is not None}
        yield
        fake.propagated = {}

    monkeypatch.setattr(tracing, "_client", fake)
    monkeypatch.setattr(tracing, "_propagate", propagate)
    return fake


def test_a_tutor_turn_is_one_trace(app, lf):
    owner = new_user(app)
    c = setup_course(owner)
    s = student_in(app, c)
    chat = new_chat(s, c["id"])
    done = ask(s, chat, "Why does Bayes theorem need a prior?")[-1]["message"]
    root = next(o for o in lf.obs if o.kind == "span")
    assert root.name == "tutor_turn" and root.ended and root.fields["output"] == done["content"]
    assert root.trace["session_id"] == f"chat-{chat}" and root.trace["metadata"]["course_id"] == str(c["id"])
    assert root.trace["trace_name"] == "tutor_turn" and root.trace["user_id"] and f"course:{c['id']}" in root.trace["tags"]
    meta = root.fields["metadata"]
    assert meta["message_id"] == done["id"] and meta["leaked"] is False and meta["retrieved"] and meta["cited"]
    gens = [o for o in lf.obs if o.kind == "generation" and o.trace_id == root.trace_id]
    assert "tutor" in {g.name for g in gens} and all(g.fields["parent"] == root.id and g.ended for g in gens)
    assert all(g.trace["trace_name"] == "tutor_turn" and g.trace["session_id"] == f"chat-{chat}" for g in gens)
    assert not any(o.trace_id == root.trace_id for o in lf.obs if o.name in ("mismatch", "starters"))  # setup: own traces
    tutor = next(g for g in gens if g.name == "tutor")
    assert tutor.fields["input"][-1]["content"] == "Why does Bayes theorem need a prior?"
    assert tutor.fields["output"]


def test_solution_text_is_never_sent(app, lf):
    owner = new_user(app)
    c = setup_course(owner)
    s = student_in(app, c)
    ask(s, new_chat(s, c["id"], "pset", c["p1"]), "I think it's 1/2. Is that the final answer?")
    checker = next(o for o in lf.obs if o.name == "checker")
    assert checker.fields["input"] is None and checker.fields["metadata"] == {"input_withheld": True}
    assert all(SOLUTION_PHRASE not in json.dumps(o.fields.get("input"), default=str) for o in lf.obs)


def test_leak_blocked_turn_is_tagged(app, lf, monkeypatch):
    from app import llm
    owner = new_user(app)
    c = setup_course(owner)
    s = student_in(app, c)
    monkeypatch.setattr(llm, "mock_tutor_text", lambda system: SOL1)
    assert ask(s, new_chat(s, c["id"], "pset", c["p1"]), "help me")[-1]["message"]["content"] == SAFE_REPLY
    root = next(o for o in lf.obs if o.kind == "span")
    assert root.fields["metadata"]["leaked"] is True and root.fields["level"] == "WARNING"
    assert root.fields["output"] == SAFE_REPLY
    outcome = next(o for o in lf.obs if o.name == "outcome" and o.trace_id == root.trace_id)
    assert "leak-blocked" in outcome.trace["tags"] and "mode:graded" in outcome.trace["tags"]


def test_qna_answer_is_one_trace(app, lf):
    owner = new_user(app)
    c = setup_course(owner)
    s = student_in(app, c)
    r = s.post(f"/api/courses/{c['id']}/qna", json={"question": "What does Bayes theorem say about the prior?"})
    assert r.status_code == 200, r.text
    root = next(o for o in lf.obs if o.kind == "span")
    assert root.name == "qna_answer" and root.ended
    assert any(o.name == "qna_answer" and o.kind == "generation" and o.trace_id == root.trace_id for o in lf.obs)


def test_broken_tracer_never_breaks_a_reply(app, monkeypatch):
    class Broken:
        def __getattr__(self, name):
            raise RuntimeError("langfuse down")

    monkeypatch.setattr(tracing, "_client", Broken())
    owner = new_user(app)
    c = setup_course(owner)
    s = student_in(app, c)
    done = ask(s, new_chat(s, c["id"]), "Why does Bayes theorem need a prior?")[-1]
    assert done["type"] == "done" and done["message"]["content"]


def test_off_without_keys(app):
    assert tracing.client() is None
    t = tracing.Trace("x", {"course_id": 1}, "hi")
    assert "trace_id" not in t.attr
    t.end("ok")


def test_an_illustration_is_one_trace(app, lf):
    owner = new_user(app)
    c = setup_course(owner)
    s = student_in(app, c)
    chat = new_chat(s, c["id"])
    ask(s, chat, "Can you explain Bayes theorem and conditional probability?")
    ill = s.post(f"/api/chats/{chat}/illustrate", json={}).json()
    root = next(o for o in lf.obs if o.kind == "span" and o.name == "illustration")
    assert root.ended and root.trace["session_id"] == f"chat-{chat}" and root.trace["trace_name"] == "illustration"
    assert root.fields["output"]["skill"] == ill["skill"] and root.fields["metadata"]["illustration_id"] == ill["id"]
    assert root.fields["metadata"]["routed"] is True and root.fields["metadata"]["retrieved"]
    gens = {o.name for o in lf.obs if o.kind == "generation" and o.trace_id == root.trace_id}
    assert {"illustrate_route", "illustrate_gen"} <= gens
    outcome = next(o for o in lf.obs if o.name == "outcome" and o.trace_id == root.trace_id)
    assert f"skill:{ill['skill']}" in outcome.trace["tags"]


def test_leak_blocked_illustration_is_tagged(app, lf, monkeypatch):
    from app import llm
    owner = new_user(app)
    c = setup_course(owner)
    s = student_in(app, c)
    chat = new_chat(s, c["id"], "pset", c["p1"])
    ask(s, chat, "Help me with Problem 1 on tossing a fair coin three times.")
    real = llm.complete
    monkeypatch.setattr(llm, "complete", lambda purpose, messages, **kw: json.dumps(
        {"title": "Leak", "subtitle": SOL1, "formula": "3/8", "beats": [{"step": 1, "heading": "Answer", "caption": SOL1}]})
        if purpose == "illustrate_gen" else real(purpose, messages, **kw))
    assert s.post(f"/api/chats/{chat}/illustrate", json={}).status_code == 200
    root = next(o for o in lf.obs if o.kind == "span" and o.name == "illustration")
    assert root.fields["metadata"]["leaked"] is True and root.fields["level"] == "WARNING"
    outcome = next(o for o in lf.obs if o.name == "outcome" and o.trace_id == root.trace_id)
    assert {"leak-blocked", "mode:graded"} <= set(outcome.trace["tags"])
    assert all(SOLUTION_PHRASE not in json.dumps(o.fields.get("input"), default=str) for o in lf.obs)


def test_retrieval_is_a_step_with_scores(app, lf, monkeypatch):
    from app import llm
    real = llm._mock_complete
    monkeypatch.setattr(llm, "_mock_complete", lambda purpose, messages, attr: "why does Bayes theorem need a prior"
                        if purpose == "rewrite" else real(purpose, messages, attr))
    owner = new_user(app)
    c = setup_course(owner)
    s = student_in(app, c)
    chat = new_chat(s, c["id"])
    ask(s, chat, "Why does Bayes theorem need a prior?")
    ask(s, chat, "why?")  # short follow-up: rewritten into a standalone query
    root = [o for o in lf.obs if o.name == "tutor_turn"][-1]
    step = next(o for o in lf.obs if o.name == "retrieval" and o.trace_id == root.trace_id)
    assert step.kind == "retriever" and step.fields["parent"] == root.id and step.ended
    assert step.fields["input"] == "why?" and step.fields["metadata"]["rewritten"] is True
    out = step.fields["output"]
    assert out["query"] != "why?" and out["chunks"]
    assert [ch["chunk_id"] for ch in out["chunks"]] == [r["chunk_id"] for r in root.fields["metadata"]["retrieved"]]
    assert any(ch.get("bm25") for ch in out["chunks"]) and all("bm25_rank" in ch for ch in out["chunks"])
    rewrite = next(o for o in lf.obs if o.name == "rewrite" and o.trace_id == root.trace_id)
    assert rewrite.fields["parent"] == step.id  # the rewrite call nests under retrieval


def test_qna_and_illustration_retrieval_steps(app, lf):
    owner = new_user(app)
    c = setup_course(owner)
    s = student_in(app, c)
    s.post(f"/api/courses/{c['id']}/qna", json={"question": "What does Bayes theorem say about the prior?"})
    qa_root = next(o for o in lf.obs if o.kind == "span" and o.name == "qna_answer")
    qa_step = next(o for o in lf.obs if o.name == "retrieval" and o.trace_id == qa_root.trace_id)
    assert qa_step.fields["output"]["chunks"] and "past_qa" in qa_step.fields["metadata"]
    chat = new_chat(s, c["id"])
    ask(s, chat, "Can you explain Bayes theorem and conditional probability?")
    s.post(f"/api/chats/{chat}/illustrate", json={})
    ill_root = next(o for o in lf.obs if o.kind == "span" and o.name == "illustration")
    ill_step = next(o for o in lf.obs if o.name == "retrieval" and o.trace_id == ill_root.trace_id)
    assert ill_step.fields["metadata"]["hybrid"] is True and ill_step.fields["output"]["chunks"]


def test_explain_reports_scores_and_ranks():
    import numpy as np
    from app.retrieval import Chunk, Index
    chunks = [Chunk(1, "d1", "Bayes", "notes", 1, "bayes theorem prior posterior"),
              Chunk(2, "d2", "Variance", "notes", 1, "variance spread mean")]
    v1, v2 = np.array([1.0, 0.0], dtype=np.float32), np.array([0.0, 1.0], dtype=np.float32)
    idx = Index(chunks, [v1, v2])
    rows = idx.explain("bayes prior", v1, chunks)
    assert rows[0]["bm25_rank"] == 1 and rows[0]["bm25"] > 0 and rows[0]["cosine"] == 1.0 and rows[0]["cosine_rank"] == 1
    assert rows[1]["bm25"] is None and rows[1]["bm25_rank"] is None and rows[1]["cosine_rank"] == 2
    assert "cosine" not in idx.explain("bayes", None, chunks)[0]
