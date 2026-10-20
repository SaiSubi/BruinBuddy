"""Upload the public (citable) PDFs to the private Supabase Storage bucket.  Tutor-only solution PDFs are never uploaded.

Reads the local ingested SQLite DB for the file list and SUPABASE_URL / SUPABASE_SERVICE_KEY from the environment
or .env.production.  Safe to re-run (uploads overwrite).  From the repo root:
    backend/.venv/bin/python deploy/upload_pdfs.py
"""
import os
import sqlite3
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "18.05-spring-2022" / "static_resources"

env_file = ROOT / ".env.production"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

url = os.environ.get("SUPABASE_URL", "").rstrip("/")
key = os.environ.get("SUPABASE_SERVICE_KEY", "")
bucket = os.environ.get("STORAGE_BUCKET", "course-pdfs")
if not (url and key):
    sys.exit("Set SUPABASE_URL and SUPABASE_SERVICE_KEY (in .env.production).")

headers = {"apikey": key}
if key.startswith("eyJ"):
    headers["Authorization"] = f"Bearer {key}"

con = sqlite3.connect(ROOT / "data" / "bruinbuddy.db")
public = [r[0] for r in con.execute("SELECT file_name FROM documents WHERE tutor_only=0")]
secret = {r[0] for r in con.execute("SELECT file_name FROM documents WHERE tutor_only=1")}
assert public and not (set(public) & secret), "a file is both public and tutor-only"
assert not any("_sol" in n for n in public), "a solution file is marked public"

with httpx.Client(timeout=60, headers=headers) as c:
    r = c.post(f"{url}/storage/v1/bucket", json={"id": bucket, "name": bucket, "public": False})
    if r.status_code not in (200, 201, 400, 409):  # 400/409: already exists
        sys.exit(f"could not create bucket: {r.status_code} {r.text[:200]}")
    if r.status_code in (200, 201):
        print(f"created private bucket '{bucket}'")
    done = 0
    for name in public:
        r = c.post(f"{url}/storage/v1/object/{bucket}/{name}", content=(SRC / name).read_bytes(),
                   headers={"Content-Type": "application/pdf", "x-upsert": "true"})
        if r.status_code not in (200, 201):
            sys.exit(f"upload failed for {name}: {r.status_code} {r.text[:200]}")
        done += 1
    print(f"uploaded {done} public PDFs to bucket '{bucket}' (private)")
