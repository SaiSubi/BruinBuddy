"""Optional Langfuse tracing of model calls, for analysing and improving answers. Off unless LANGFUSE_PUBLIC_KEY
and LANGFUSE_SECRET_KEY are set.

An answer (a tutor turn, a Q&A reply, an assignment turn) opens a `Trace`; its `attr` carries the trace id, so every
`llm` call made with that attr lands in the same trace even when the turn moves between threads. Calls made outside
an answer (memory, starters, extraction) get a trace of their own. Prompts that contain confidential solution text
(the checker, the leak guard, the assignment verifier and drafter, the upload mismatch check) are sent without their
input. Tracing must never break a reply, so every failure here is swallowed.

Langfuse SDK v5 keeps user, session, tags and trace name on each observation, set through `propagate_attributes`
around the call that creates it (synchronous, so it is safe in streamed turns that hop threads).
"""
import logging
from contextlib import contextmanager, nullcontext
from typing import Any, Iterator

from . import config

SECRET_PURPOSES = frozenset({"checker", "guard", "assignment_verify", "assignment_gen", "mismatch"})

log = logging.getLogger(__name__)
_client: Any = None
_propagate: Any = None  # langfuse.propagate_attributes, loaded with the client


def client() -> Any:
    global _client, _propagate
    if _client is None and config.LANGFUSE_PUBLIC_KEY and config.LANGFUSE_SECRET_KEY:
        try:
            from langfuse import Langfuse, propagate_attributes
            _client = Langfuse(public_key=config.LANGFUSE_PUBLIC_KEY, secret_key=config.LANGFUSE_SECRET_KEY,
                               host=config.LANGFUSE_HOST, sample_rate=config.LANGFUSE_SAMPLE_RATE,
                               release=config.APP_RELEASE,
                               environment="production" if config.PRODUCTION else "development")
            _propagate = _propagate or propagate_attributes
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


def _trace_attributes(name: str, attr: dict | None, tags: list[str] | None = None):
    """Trace-level fields for the observation created inside this context."""
    attr = attr or {}
    fields: dict = {"trace_name": name,
                    "metadata": {k: str(attr[k]) for k in ("course_id", "chat_id") if attr.get(k)} or None,
                    "tags": ([f"course:{attr['course_id']}"] if attr.get("course_id") else []) + (tags or []) or None,
                    "user_id": str(attr["user_id"]) if attr.get("user_id") else None,
                    "session_id": f"chat-{attr['chat_id']}" if attr.get("chat_id") else None}
    return _propagate(**fields) if _propagate else nullcontext()


class Trace:
    """One answer. Use `.attr` for its model calls, then `.end(output, **metadata)` once (safe to call again)."""

    def __init__(self, name: str, attr: dict, input: Any) -> None:
        self.attr, self._span = dict(attr), None
        lf = client()
        if not lf:
            return
        try:
            with _trace_attributes(name, attr):
                self._span = lf.start_observation(name=name, input=input)
            self.attr.update(trace_id=self._span.trace_id, span_id=self._span.id, trace_name=name)
        except Exception:
            self._span = None

    def end(self, output: Any = None, *, tags: list[str] | None = None, **metadata: Any) -> None:
        span, self._span = self._span, None
        if not span:
            return
        try:
            span.update(output=output, metadata=metadata, **({"level": "WARNING"} if metadata.get("leaked") else {}))
            if tags:  # outcome tags are known only now: they ride on a final event in the same trace
                with _trace_attributes(self.attr["trace_name"], self.attr, tags):
                    span.create_event(name="outcome", metadata=metadata)
            span.end()
        except Exception:
            pass


class Step:
    """A stage inside an answer, such as retrieval. Model calls made with `.attr` nest under it. A no-op outside a
    traced answer; check `.on` before computing anything only the trace needs."""

    def __init__(self, name: str, attr: dict, input: Any, as_type: str = "span") -> None:
        self.attr, self._obs = dict(attr), None
        lf = client()
        if not lf or not attr.get("trace_id"):
            return
        try:
            with _trace_attributes(attr["trace_name"], attr):
                self._obs = lf.start_observation(name=name, as_type=as_type, input=input,
                                                 trace_context={"trace_id": attr["trace_id"],
                                                                "parent_span_id": attr["span_id"]})
            self.attr["span_id"] = self._obs.id
        except Exception:
            self._obs = None

    @property
    def on(self) -> bool:
        return self._obs is not None

    def __enter__(self) -> "Step":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._obs and exc_type:
            try:
                self._obs.update(level="ERROR", status_message=exc_type.__name__)
            except Exception:
                pass
        self.end()

    def end(self, output: Any = None, **metadata: Any) -> None:
        obs, self._obs = self._obs, None
        if not obs:
            return
        try:
            obs.update(output=output, metadata=metadata or None)
            obs.end()
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
            secret = purpose in SECRET_PURPOSES
            with _trace_attributes((attr or {}).get("trace_name") or purpose, attr):
                obs = lf.start_observation(as_type="generation", name=purpose, model=model, trace_context=ctx,
                                           input=None if secret else messages,
                                           metadata={"input_withheld": True} if secret else None)
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
