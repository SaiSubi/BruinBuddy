"""Optional Langfuse tracing of model calls, for analysing and improving answers. Off unless LANGFUSE_PUBLIC_KEY
and LANGFUSE_SECRET_KEY are set.

An answer (a tutor turn, a Q&A reply, an assignment turn) opens a `Trace`; its `attr` carries the trace id, so every
`llm` call made with that attr lands in the same trace even when the turn moves between threads. Calls made outside
an answer (memory, starters, extraction) get a trace of their own. Prompts that contain confidential solution text
(the checker, the leak guard, the assignment verifier and drafter, the upload mismatch check) are sent without their input. Tracing must never
break a reply, so every failure here is swallowed.
"""
import logging
from contextlib import contextmanager
from typing import Any, Iterator

from . import config

SECRET_PURPOSES = frozenset({"checker", "guard", "assignment_verify", "assignment_gen", "mismatch"})

log = logging.getLogger(__name__)
_client: Any = None


def client() -> Any:
    global _client
    if _client is None and config.LANGFUSE_PUBLIC_KEY and config.LANGFUSE_SECRET_KEY:
        try:
            from langfuse import Langfuse
            _client = Langfuse(public_key=config.LANGFUSE_PUBLIC_KEY, secret_key=config.LANGFUSE_SECRET_KEY,
                               host=config.LANGFUSE_HOST, sample_rate=config.LANGFUSE_SAMPLE_RATE,
                               environment="production" if config.PRODUCTION else "development")
        except Exception:
            log.exception("Langfuse could not start; tracing is off")
            _client = False
    return _client or None


def flush() -> None:
    lf = client()
    if lf:
        try:
            lf.flush()
        except Exception:
            pass


def _trace_fields(attr: dict | None) -> dict:
    attr = attr or {}
    fields: dict = {"metadata": {"course_id": attr.get("course_id"), "chat_id": attr.get("chat_id")}}
    if attr.get("course_id"):
        fields["tags"] = [f"course:{attr['course_id']}"]
    if attr.get("user_id"):
        fields["user_id"] = str(attr["user_id"])
    if attr.get("chat_id"):
        fields["session_id"] = f"chat-{attr['chat_id']}"
    return fields


class Trace:
    """One answer. Use `.attr` for its model calls, then `.end(output, **metadata)` once (safe to call again)."""

    def __init__(self, name: str, attr: dict, input: Any) -> None:
        self.attr, self._span = dict(attr), None
        lf = client()
        if not lf:
            return
        try:
            self._span = lf.start_span(name=name, input=input)
            self._span.update_trace(name=name, input=input, **_trace_fields(attr))
            self.attr.update(trace_id=self._span.trace_id, span_id=self._span.id)
        except Exception:
            self._span = None

    def end(self, output: Any = None, *, tags: list[str] | None = None, **metadata: Any) -> None:
        span, self._span = self._span, None
        if not span:
            return
        try:
            span.update(output=output, metadata=metadata, level="WARNING" if metadata.get("leaked") else None)
            fields = _trace_fields(self.attr)
            extra = {"tags": fields.get("tags", []) + tags} if tags else {}
            span.update_trace(output=output, metadata={**fields["metadata"], **metadata}, **extra)
            span.end()
        except Exception:
            pass


class Generation:
    """What `llm` fills in while a call runs."""

    def __init__(self) -> None:
        self.output: str | None = None
        self.model: str | None = None
        self.usage: tuple[int | None, int | None, float | None] | None = None


@contextmanager
def generation(purpose: str, messages: list[dict], model: str, attr: dict | None) -> Iterator[Generation]:
    g, obs = Generation(), None
    lf = client()
    if lf:
        try:
            ctx = {"trace_id": attr["trace_id"], "parent_span_id": attr["span_id"]} if attr and attr.get("trace_id") \
                else None
            obs = lf.start_generation(name=purpose, model=model, trace_context=ctx,
                                      input=None if purpose in SECRET_PURPOSES else messages,
                                      metadata={"input_withheld": True} if purpose in SECRET_PURPOSES else None)
            if not ctx:
                obs.update_trace(name=purpose, **_trace_fields(attr))
        except Exception:
            obs = None
    try:
        yield g
    except BaseException as e:
        if obs:
            try:
                obs.update(level="ERROR", status_message=type(e).__name__)
            except Exception:
                pass
        raise
    finally:
        if obs:
            try:
                fields: dict = {"output": g.output}
                if g.model:
                    fields["model"] = g.model
                if g.usage:
                    pt, ct, cost = g.usage
                    fields["usage_details"] = {"input": pt or 0, "output": ct or 0}
                    if cost is not None:
                        fields["cost_details"] = {"total": float(cost)}
                obs.update(**fields)
                obs.end()
            except Exception:
                pass
