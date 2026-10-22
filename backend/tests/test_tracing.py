"""Langfuse tracing (tracing.py) against a fake client: one trace per answer, solution text never sent, and a
broken tracer never breaks a reply."""
import json

import pytest

from app import tracing
from app.tutor import SAFE_REPLY
from conftest import SOL1, ask, new_chat, new_user, setup_course, student_in

SOLUTION_PHRASE = "three favorable sequences"


class FakeObs:
    def __init__(self, lf, kind, name, trace_id, **kw):
        self.lf, self.kind, self.name, self.trace_id, self.id = lf, kind, name, trace_id, f"obs{len(lf.obs)}"
        self.fields, self.trace, self.ended = dict(kw), {}, False

    def update(self, **kw):
        self.fields.update(kw)

    def update_trace(self, **kw):
        self.trace.update(kw)

    def end(self):
        self.ended = True


class FakeLangfuse:
    def __init__(self):
        self.obs: list[FakeObs] = []

    def _new(self, kind, name, trace_context=None, **kw):
        tid = (trace_context or {}).get("trace_id") or f"t{len(self.obs)}"
        o = FakeObs(self, kind, name, tid, parent=(trace_context or {}).get("parent_span_id"), **kw)
        self.obs.append(o)
        return o

    def start_span(self, *, name, **kw):
        return self._new("span", name, **kw)

    def start_generation(self, *, name, **kw):
        return self._new("generation", name, **kw)

    def flush(self):
        pass


@pytest.fixture
def lf(monkeypatch):
    fake = FakeLangfuse()
    monkeypatch.setattr(tracing, "_client", fake)
    return fake


def test_a_tutor_turn_is_one_trace(app, lf):
    owner = new_user(app)
    c = setup_course(owner)
    s = student_in(app, c)
    chat = new_chat(s, c["id"])
    done = ask(s, chat, "Why does Bayes theorem need a prior?")[-1]["message"]
    root = next(o for o in lf.obs if o.kind == "span")
    assert root.name == "tutor_turn" and root.ended and root.fields["output"] == done["content"]
    assert root.trace["session_id"] == f"chat-{chat}" and root.trace["metadata"]["course_id"] == c["id"]
    meta = root.fields["metadata"]
    assert meta["message_id"] == done["id"] and meta["leaked"] is False and meta["retrieved"] and meta["cited"]
    gens = [o for o in lf.obs if o.kind == "generation" and o.trace_id == root.trace_id]
    assert "tutor" in {g.name for g in gens} and all(g.fields["parent"] == root.id and g.ended for g in gens)
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
    assert "leak-blocked" in root.trace["tags"] and root.trace["output"] == SAFE_REPLY


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
