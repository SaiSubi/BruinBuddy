"""OpenRouter client (OpenAI-compatible).  BB_MOCK_LLM=1 swaps in a fake for dev/testing without a key.

Every call takes `attr` ({course_id, user_id, chat_id}) so its token usage is attributed in usage_log; token
allowances and the course ceiling are computed from those rows. Attribution is passed explicitly (not through a
context variable) because a streamed turn runs across several worker threads.
"""
import hashlib
import json
import re
from typing import Iterator

from openai import OpenAI

from . import config
from .db import db, now


class LLMUnavailable(RuntimeError):
    pass


_client: OpenAI | None = None
MOCK_CALLS: list[dict] = []  # mock mode only: every call's purpose and messages, for tests


def client() -> OpenAI:
    global _client
    if not config.OPENROUTER_API_KEY:
        raise LLMUnavailable("The AI service isn't configured on this server (OPENROUTER_API_KEY is missing).")
    if _client is None:
        _client = OpenAI(api_key=config.OPENROUTER_API_KEY, base_url=config.OPENROUTER_BASE_URL,
                         timeout=config.LLM_TIMEOUT_SECONDS, max_retries=2,
                         default_headers={"X-Title": "BruinBuddy (class project)"})
    return _client


def log_usage(purpose: str, model: str, prompt_tokens: int | None, completion_tokens: int | None,
              cost: float | None, attr: dict | None, counted: bool = True) -> None:
    """`counted=False` records the cost but leaves total_tokens at 0, so it doesn't use up allowances or the ceiling."""
    attr = attr or {}
    total = (prompt_tokens or 0) + (completion_tokens or 0) if counted else 0
    try:
        with db() as conn:
            conn.execute("INSERT INTO usage_log(ts,purpose,model,prompt_tokens,completion_tokens,cost,course_id,user_id,"
                         "chat_id,total_tokens) VALUES(?,?,?,?,?,?,?,?,?,?)",
                         (now(), purpose, model, prompt_tokens, completion_tokens, cost, attr.get("course_id"),
                          attr.get("user_id"), attr.get("chat_id"), total))
    except Exception:
        pass  # logging must never break a reply


def _log(purpose: str, model: str, usage, attr: dict | None, counted: bool = True) -> None:
    if not usage:
        return
    cost = getattr(usage, "cost", None)
    if cost is None and getattr(usage, "model_extra", None):
        cost = usage.model_extra.get("cost")
    log_usage(purpose, model, getattr(usage, "prompt_tokens", None), getattr(usage, "completion_tokens", None),
              cost, attr, counted)


def _extra(effort: str) -> dict:
    return {"reasoning": {"effort": effort}}


def complete(purpose: str, messages: list[dict], *, model: str | None = None, max_tokens: int = 600,
             effort: str = "low", attr: dict | None = None) -> str:
    if config.MOCK_LLM:
        return _mock_complete(purpose, messages, attr)
    model = model or config.HELPER_MODEL
    r = client().chat.completions.create(model=model, messages=messages, max_tokens=max_tokens,
                                         extra_body=_extra(effort))
    _log(purpose, model, r.usage, attr)
    return r.choices[0].message.content or ""


def _stream_once(purpose: str, messages: list[dict], model: str, max_tokens: int, effort: str,
                 attr: dict | None) -> Iterator[str]:
    s = client().chat.completions.create(model=model, messages=messages, max_tokens=max_tokens, stream=True,
                                         stream_options={"include_usage": True}, extra_body=_extra(effort))
    for ev in s:
        if ev.usage:
            _log(purpose, model, ev.usage, attr)
        if ev.choices and ev.choices[0].delta.content:
            yield ev.choices[0].delta.content


def stream(purpose: str, messages: list[dict], *, model: str | None = None, max_tokens: int = 1500,
           effort: str = "medium", attr: dict | None = None) -> Iterator[str]:
    """Stream a reply. If the model fails before sending any text and TUTOR_FALLBACK_MODEL is set, retry once."""
    if config.MOCK_LLM:
        yield from _mock_stream(messages, attr)
        return
    model = model or config.TUTOR_MODEL
    sent = False
    try:
        for delta in _stream_once(purpose, messages, model, max_tokens, effort, attr):
            sent = True
            yield delta
    except LLMUnavailable:
        raise
    except Exception:
        fallback = config.TUTOR_FALLBACK_MODEL
        if sent or not fallback or fallback == model:
            raise
        yield from _stream_once(purpose, messages, fallback, max_tokens, effort, attr)


def can_embed() -> bool:
    return config.MOCK_LLM or bool(config.OPENROUTER_API_KEY)


def embed_model() -> str:
    """Stored with each vector: vectors from different models can't be compared."""
    return "mock" if config.MOCK_LLM else config.EMBED_MODEL


def embed_floor() -> float:
    """Minimum cosine similarity for an embedding match (the mock's hashed words: at least one shared word)."""
    return 1e-6 if config.MOCK_LLM else config.EMBED_MIN_SIMILARITY


def embed(purpose: str, texts: list[str], *, attr: dict | None = None) -> list[list[float]]:
    """Embedding vectors, in order. Their usage is logged with its cost but not counted against token allowances:
    embedding a whole course takes far more tokens than a tutor turn while costing about a cent."""
    if config.MOCK_LLM:
        log_usage(purpose, "mock", 10 * len(texts), 0, 0.0, attr, counted=False)
        return [_mock_vector(t) for t in texts]
    out: list[list[float]] = []
    for i in range(0, len(texts), 128):
        r = client().embeddings.create(model=config.EMBED_MODEL, input=texts[i:i + 128])
        _log(purpose, config.EMBED_MODEL, r.usage, attr, counted=False)
        out += [d.embedding for d in sorted(r.data, key=lambda d: d.index)]
    return out


def parse_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return {}
    try:
        out = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}
    return out if isinstance(out, dict) else {}


# ---- mock (dev and tests only) ---------------------------------------------------------
MOCK_TOKENS = (900, 100)  # pretend usage per call, so allowances can be exercised without a key


def _mock_record(purpose: str, messages: list[dict], attr: dict | None) -> None:
    MOCK_CALLS.append({"purpose": purpose, "messages": messages})
    del MOCK_CALLS[:-200]
    log_usage(purpose, "mock", MOCK_TOKENS[0], MOCK_TOKENS[1], 0.0, attr)


def mock_tutor_text(system: str) -> str:
    has_source = "[S1]" in system
    if "Graded, hints only" in system:
        return ("This looks like an assigned problem, so I won't give the answer. What have you tried so far? "
                "A good first hint: re-read the definition in the notes and write down what is given. [S1]")
    if "Practice, full help" in system:
        return "(mock tutor) This set is for practice. Try a first step and I'll walk through the full method with you. [S1]"
    if "Solutions open" in system:
        return "(mock tutor) The solutions are open now. Here is how the official solution approaches it. [S1]"
    if "QUIZ MODE" in system and has_source:
        return "(mock tutor) Quiz question 1: what does the course notes' definition say here? [S1]"
    if "REVIEW MODE" in system and has_source:
        return "(mock tutor) Review plan: 1. Re-read the definitions [S1]. 2. Work the examples [S2]. Ready for a check?"
    if has_source:
        return "(mock tutor) Here is what the course materials say about that. [S1] What part would you like to check? [S2]"
    return "[NC] (mock tutor) I can't find that in the course materials."


def _mock_vector(text: str, dim: int = 4096) -> list[float]:
    """Hashed bag of words: texts sharing words point the same way, so tests can exercise the dense path."""
    from .retrieval import tokens
    v = [0.0] * dim
    for t in tokens(text):
        v[int(hashlib.md5(t.encode()).hexdigest(), 16) % dim] += 1.0
    return v


def _mock_stream(messages: list[dict], attr: dict | None) -> Iterator[str]:
    _mock_record("tutor", messages, attr)
    text = mock_tutor_text(messages[0]["content"])
    for i in range(0, len(text), 12):
        yield text[i:i + 12]


def _mock_complete(purpose: str, messages: list[dict], attr: dict | None) -> str:
    _mock_record(purpose, messages, attr)
    last = messages[-1]["content"]
    if purpose == "rewrite":
        return last.split("LATEST MESSAGE:")[-1].strip()
    if purpose == "checker":
        return json.dumps({"attempt_status": "none", "feedback": "Ask what they tried; hint at the definition."})
    if purpose == "guard":
        return json.dumps({"leaks": False})
    if purpose == "memory":
        topic = re.sub(r"\s+", " ", last.split("STUDENT:")[-1].split("TUTOR:")[0]).strip()[:60]
        return json.dumps({"ops": [{"op": "add", "text": f"Recently asked about: {topic}"}]})
    if purpose == "starters":
        titles = re.findall(r"^### (.+)$", last, re.M)[:4]
        return json.dumps({"questions": [f"What are the key ideas in {t}?" for t in titles]})
    if purpose == "mismatch":
        return json.dumps({"category": "", "warning": ""})
    return ""
