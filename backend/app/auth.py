"""Tokens and passwords.

- Supabase access tokens (production): verified locally against the project's public JWKS (ES256), so no
  Supabase call per request. Legacy HS256 tokens are accepted only if SUPABASE_JWT_SECRET is set.
- Local session tokens (development): HMAC-SHA256 over the user id and expiry. No cookies, so the Vercel
  frontend and the Fly backend can live on different domains.
- File tokens: authorise one document for a short time, with a scope (public material, or staff access).
"""
import hashlib
import hmac
import secrets
import time

import jwt

from . import config

_DEV_KEY = "dev-insecure-key-do-not-use-in-production"


def _key() -> bytes:
    return (config.SECRET_KEY or _DEV_KEY).encode()


def _sign(msg: str) -> str:
    return hmac.new(_key(), msg.encode(), hashlib.sha256).hexdigest()[:40]


def codes_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


# ---- local session tokens ------------------------------------------------------------
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


# ---- signed one-off links (file links, test checkout) --------------------------------
def make_file_token(doc_id: str, staff: bool = False) -> str:
    exp = int(time.time()) + config.FILE_TOKEN_TTL_SECONDS
    scope = "s" if staff else "p"
    return f"{exp}.{scope}.{_sign(f'f.{doc_id}.{exp}.{scope}')}"


def verify_file_token(doc_id: str, token: str) -> str | None:
    """Return the scope ('p' public, 's' staff) if the token is valid for this document, else None."""
    parts = (token or "").split(".")
    if len(parts) != 3 or not parts[0].isdigit() or parts[1] not in ("p", "s"):
        return None
    exp, scope, sig = parts
    if not hmac.compare_digest(_sign(f"f.{doc_id}.{exp}.{scope}"), sig) or int(exp) <= time.time():
        return None
    return scope


def make_signed(purpose: str, value: str, ttl: int) -> str:
    exp = int(time.time()) + ttl
    return f"{exp}.{_sign(f'{purpose}.{value}.{exp}')}"


def verify_signed(purpose: str, value: str, token: str) -> bool:
    exp, _, sig = (token or "").partition(".")
    if not exp.isdigit() or not sig:
        return False
    return hmac.compare_digest(_sign(f"{purpose}.{value}.{exp}"), sig) and int(exp) > time.time()


# ---- passwords (local accounts only) ---------------------------------------------------
_SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **_SCRYPT)
    return f"scrypt${salt.hex()}${dk.hex()}"


def check_password(password: str, stored: str | None) -> bool:
    try:
        algo, salt, digest = (stored or "").split("$")
    except ValueError:
        return False
    if algo != "scrypt":
        return False
    dk = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), dklen=32, **_SCRYPT)
    return hmac.compare_digest(dk.hex(), digest)


# ---- Supabase access tokens --------------------------------------------------------------
_jwks_client = None


def _jwks():
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(f"{config.SUPABASE_URL}/auth/v1/.well-known/jwks.json",
                                       cache_keys=True, lifespan=3600, timeout=10)
    return _jwks_client


def verify_supabase_token(token: str) -> dict | None:
    """Return the token's claims if it is a valid, unexpired Supabase access token for this project."""
    if not token or not config.SUPABASE_URL:
        return None
    try:
        alg = jwt.get_unverified_header(token).get("alg")
        if alg == "HS256":
            if not config.SUPABASE_JWT_SECRET:
                return None
            key, algorithms = config.SUPABASE_JWT_SECRET, ["HS256"]
        else:
            key, algorithms = _jwks().get_signing_key_from_jwt(token).key, ["ES256", "RS256"]
        claims = jwt.decode(token, key, algorithms=algorithms, audience="authenticated",
                            issuer=f"{config.SUPABASE_URL}/auth/v1", options={"require": ["exp", "sub"]})
    except jwt.PyJWTError:
        return None
    if claims.get("role") != "authenticated" or claims.get("is_anonymous"):
        return None
    return claims
