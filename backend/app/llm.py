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
             effort: str = "low", attr: dict | None) -> str:
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
    if purpose == "assignment_gen":
        steps = [("Set up the model", "Which quantities does the problem give you, and what are you asked to find?",
                  "The given quantities and the unknown, named with the course's notation", 30),
                 ("Apply the key rule", "Which rule or formula connects the given quantities to the unknown?",
                  "The rule that links them, written out", 30),
                 ("Final Answer", "Put it together: what is the final answer?", "The final answer from the notes", 40)]
        return json.dumps({"checkpoints": [
            {"title": f"Checkpoint {i + 1}: {t}" if t != "Final Answer" else t, "prompt": p, "target_answer": a,
             "rubric": f"Accept an answer equivalent to: {a}", "hint": "Re-read the problem statement carefully.",
             "points": pts} for i, (t, p, a, pts) in enumerate(steps)]})
    if purpose == "assignment_verify":
        target = last.split("CONFIDENTIAL TARGET ANSWER:", 1)[-1].split("\n\n", 1)[0].strip()
        said = last.split("STUDENT MESSAGE:", 1)[-1]
        ok = bool(target) and re.sub(r"\s+", "", target).lower() in re.sub(r"\s+", "", said).lower()
        return json.dumps({"passed": ok, "feedback": "" if ok else "Revisit what the problem gives you."})
    if purpose == "assignment_tutor":
        system = messages[0]["content"]
        if "STAGE: complete" in system:
            return "(mock tutor) Well done, you finished the assignment. Here is the path you took, step by step."
        if "STAGE: advance" in system:
            return "(mock tutor) Nice work, that checkpoint is done. On to the next question: what comes next?"
        if "STAGE: hint" in system:
            return "(mock tutor) Here's a nudge: re-read the problem statement. What does it give you?"
        return "(mock tutor) Not quite yet. What does the problem tell you, and what is it asking for?"
    if purpose == "illustrate_route":
        low = last.lower()
        if any(w in low for w in ("remotion", "motion graphics", "kinetic", "spring", "metric", "counter")):
            skill = "remotion_motion"
        elif any(w in low for w in ("galton", "urn", "machine", "apparatus", "coin", "dice", "isometric")):
            skill = "anatomy_isometric"
        elif any(w in low for w in ("workflow", "flowchart", "pipeline", "hypothesis", "markov", "step")):
            skill = "explainer_diagram"
        elif any(w in low for w in ("whiteboard", "story", "overview", "summary")):
            skill = "explainer_storyboard"
        else:
            skill = "manim_3b1b"
        return json.dumps({
            "skill": skill,
            "concept": "Probability & Conditioning Intuition",
            "title": "Visualizing Probability & Conditioning",
            "rationale": f"Selected {skill} to render an interactive visual model of the concept.",
        })
    if purpose == "illustrate_gen":
        return json.dumps({
            "title": "Visualizing Probability & Conditioning",
            "subtitle": "How prior belief and likelihood combine to shape the distribution",
            "formula": "P(A|B) = P(B|A) · P(A) / P(B)",
            "param_label": "Parameter p",
            "param_min": 0.1,
            "param_max": 0.9,
            "param_step": 0.05,
            "param_default": 0.5,
            "secondary_label": "Trials N",
            "secondary_min": 4,
            "secondary_max": 18,
            "secondary_step": 1,
            "secondary_default": 10,
            "beats": [
                {
                    "step": 1,
                    "heading": "1. Prior Setup",
                    "caption": "Start with the baseline distribution before conditioning on new observations.",
                    "highlight": "Prior P(A)",
                    "value_hint": 0.35,
                },
                {
                    "step": 2,
                    "heading": "2. Likelihood Weighting",
                    "caption": "Each outcome is scaled by how likely it is to produce the observed evidence.",
                    "highlight": "Likelihood P(B|A)",
                    "value_hint": 0.55,
                },
                {
                    "step": 3,
                    "heading": "3. Interactive Sweep",
                    "caption": "Drag the parameter slider to see how shifting p moves the center of mass.",
                    "highlight": "Parameter Sweep",
                    "value_hint": 0.75,
                },
                {
                    "step": 4,
                    "heading": "4. Renormalized Posterior",
                    "caption": "Dividing by P(B) restores total probability to 1 across the restricted sample space.",
                    "highlight": "Posterior P(A|B)",
                    "value_hint": 0.5,
                },
            ],
        })
    return ""
