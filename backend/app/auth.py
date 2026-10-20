"""Stateless signed tokens (HMAC-SHA256).  No cookies, so the Vercel frontend and Fly backend can live on
different domains.  Session tokens carry a user id; file tokens authorise one document for a short time."""
import hashlib
import hmac
import time

from . import config

_DEV_KEY = "dev-insecure-key-do-not-use-in-production"


def _key() -> bytes:
    return (config.SECRET_KEY or _DEV_KEY).encode()


def _sign(msg: str) -> str:
    return hmac.new(_key(), msg.encode(), hashlib.sha256).hexdigest()[:40]


def make_session_token(user_id: int) -> str:
    exp = int(time.time()) + config.TOKEN_TTL_SECONDS
    body = f"u.{user_id}.{exp}"
    return f"{body}.{_sign(body)}"


def verify_session_token(token: str) -> int | None:
    parts = (token or "").split(".")
    if len(parts) != 4 or parts[0] != "u" or not parts[1].isdigit() or not parts[2].isdigit():
        return None
    body = ".".join(parts[:3])
    if not hmac.compare_digest(_sign(body), parts[3]):
        return None
    return int(parts[1]) if int(parts[2]) > time.time() else None


def make_file_token(doc_id: str) -> str:
    exp = int(time.time()) + config.FILE_TOKEN_TTL_SECONDS
    return f"{exp}.{_sign(f'f.{doc_id}.{exp}')}"


def verify_file_token(doc_id: str, token: str) -> bool:
    exp, _, sig = (token or "").partition(".")
    if not exp.isdigit() or not sig:
        return False
    return hmac.compare_digest(_sign(f"f.{doc_id}.{exp}"), sig) and int(exp) > time.time()


def codes_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())
