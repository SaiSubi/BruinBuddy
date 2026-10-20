"""Supabase Storage access for the public PDFs (private bucket, short-lived signed links).

The service key stays on the server; browsers only ever receive a signed URL that expires in minutes."""
from urllib.parse import quote

import httpx

from . import config


def configured() -> bool:
    return bool(config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY)


def _headers() -> dict:
    key = config.SUPABASE_SERVICE_KEY
    h = {"apikey": key}
    if key.startswith("eyJ"):  # legacy JWT-style service_role key; new sb_secret_ keys use apikey only
        h["Authorization"] = f"Bearer {key}"
    return h


def signed_url(object_name: str, expires: int = 300) -> str:
    r = httpx.post(f"{config.SUPABASE_URL}/storage/v1/object/sign/{config.STORAGE_BUCKET}/{quote(object_name)}",
                   headers=_headers(), json={"expiresIn": expires}, timeout=10)
    r.raise_for_status()
    path = r.json()["signedURL"]
    if not path.startswith("/storage/v1"):
        path = "/storage/v1" + path
    return config.SUPABASE_URL + path
