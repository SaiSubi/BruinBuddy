"""Course files: a private Supabase Storage bucket in production, data/uploads on disk in local development.

The service key stays on the server; browsers only ever receive a signed URL that expires in minutes, and only
for material the server has decided they may open (see /files in chats.py)."""
from pathlib import Path
from urllib.parse import quote

import httpx

from . import config


class NotFound(Exception):
    pass


def configured() -> bool:
    return bool(config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY)


def _headers() -> dict:
    key = config.SUPABASE_SERVICE_KEY
    h = {"apikey": key}
    if key.startswith("eyJ"):  # legacy JWT-style service_role key; new sb_secret_ keys use apikey only
        h["Authorization"] = f"Bearer {key}"
    return h


def _object_url(path: str) -> str:
    return f"{config.SUPABASE_URL}/storage/v1/object/{config.STORAGE_BUCKET}/{quote(path)}"


def _local(path: str) -> Path:
    p = (config.UPLOAD_DIR / path).resolve()
    if config.UPLOAD_DIR.resolve() not in p.parents:
        raise NotFound(path)
    return p


def put(path: str, data: bytes, content_type: str) -> None:
    if configured():
        r = httpx.post(_object_url(path), content=data, headers={**_headers(), "Content-Type": content_type,
                                                                 "x-upsert": "true"}, timeout=60)
        r.raise_for_status()
        return
    p = _local(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


def get(path: str) -> bytes:
    if configured():
        r = httpx.get(f"{config.SUPABASE_URL}/storage/v1/object/authenticated/{config.STORAGE_BUCKET}/{quote(path)}",
                      headers=_headers(), timeout=60)
        if r.status_code in (400, 404):
            raise NotFound(path)
        r.raise_for_status()
        return r.content
    p = _local(path)
    if not p.exists():
        raise NotFound(path)
    return p.read_bytes()


def delete(path: str) -> None:
    try:
        if configured():
            httpx.request("DELETE", f"{config.SUPABASE_URL}/storage/v1/object/{config.STORAGE_BUCKET}",
                          headers=_headers(), json={"prefixes": [path]}, timeout=30)
        else:
            _local(path).unlink(missing_ok=True)
    except (httpx.HTTPError, NotFound, OSError):
        pass  # a leftover file is harmless: nothing links to it any more


def signed_url(object_name: str, expires: int = 300) -> str:
    r = httpx.post(f"{config.SUPABASE_URL}/storage/v1/object/sign/{config.STORAGE_BUCKET}/{quote(object_name)}",
                   headers=_headers(), json={"expiresIn": expires}, timeout=10)
    if r.status_code in (400, 404):
        raise NotFound(object_name)
    r.raise_for_status()
    path = r.json()["signedURL"]
    if not path.startswith("/storage/v1"):
        path = "/storage/v1" + path
    return config.SUPABASE_URL + path


def local_path(storage_path: str | None, file_name: str) -> Path:
    """Local dev: uploads live under UPLOAD_DIR; the 18.05 seed's PDFs are read from the course export."""
    return _local(storage_path) if storage_path else config.PDF_DIR / file_name
