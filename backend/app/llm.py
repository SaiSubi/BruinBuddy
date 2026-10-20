"""OpenRouter client (OpenAI-compatible).  BB_MOCK_LLM=1 swaps in a fake for dev/testing without a key."""
import json
import re
from typing import Iterator

from openai import OpenAI

from . import config
from .db import db, now


class LLMUnavailable(RuntimeError):
    pass


_client: OpenAI | None = None


def client() -> OpenAI:
    global _client
    if not config.OPENROUTER_API_KEY:
        raise LLMUnavailable("OPENROUTER_API_KEY is not set. Add it to .env and restart the server.")
    if _client is None:
        _client = OpenAI(api_key=config.OPENROUTER_API_KEY, base_url=config.OPENROUTER_BASE_URL,
                         default_headers={"X-Title": "BruinBuddy (class project)"})
    return _client


def _log(purpose: str, model: str, usage) -> None:
    if not usage:
        return
    try:
        cost = getattr(usage, "cost", None)
        if cost is None and getattr(usage, "model_extra", None):
            cost = usage.model_extra.get("cost")
        with db() as conn:
            conn.execute("INSERT INTO usage_log(ts,purpose,model,prompt_tokens,completion_tokens,cost) VALUES(?,?,?,?,?,?)",
                         (now(), purpose, model, getattr(usage, "prompt_tokens", None),
                          getattr(usage, "completion_tokens", None), cost))
    except Exception:
        pass  # logging must never break a reply


def _extra(effort: str) -> dict:
    return {"reasoning": {"effort": effort}}


def complete(purpose: str, messages: list[dict], *, model: str | None = None, max_tokens: int = 600,
             effort: str = "low") -> str:
    if config.MOCK_LLM:
        return _mock_complete(purpose, messages)
    model = model or config.HELPER_MODEL
    r = client().chat.completions.create(model=model, messages=messages, max_tokens=max_tokens,
                                         extra_body=_extra(effort))
    _log(purpose, model, r.usage)
    return r.choices[0].message.content or ""


def stream(purpose: str, messages: list[dict], *, model: str | None = None, max_tokens: int = 1500,
           effort: str = "medium") -> Iterator[str]:
    if config.MOCK_LLM:
        yield from _mock_stream(messages)
        return
    model = model or config.TUTOR_MODEL
    s = client().chat.completions.create(model=model, messages=messages, max_tokens=max_tokens, stream=True,
                                         stream_options={"include_usage": True}, extra_body=_extra(effort))
    for ev in s:
        if ev.usage:
            _log(purpose, model, ev.usage)
        if ev.choices and ev.choices[0].delta.content:
            yield ev.choices[0].delta.content


def parse_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


# ---- mock (dev only) ---------------------------------------------------------------
def _mock_stream(messages: list[dict]) -> Iterator[str]:
    system = messages[0]["content"]
    has_source = "[S1]" in system
    assigned = "ASSIGNED PROBLEM" in system
    if assigned:
        text = ("This looks like an assigned problem, so I won't give the answer. What have you tried so far? "
                "A good first hint: re-read the definition in the notes and write down what is given. [S1]")
    elif has_source:
        text = "(mock tutor) Here is what the course materials say about that. [S1] What part would you like to check? [S2]"
    else:
        text = "(mock tutor) I can't find that in the course materials."
    for i in range(0, len(text), 12):
        yield text[i:i + 12]


def _mock_complete(purpose: str, messages: list[dict]) -> str:
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
    return ""
