"""Copy only the public (citable) PDFs into deploy/pdfs for the Docker image.

Reads the local ingested SQLite DB.  Tutor-only documents (problem set solutions) are never copied.
Run from the repo root:  backend/.venv/bin/python deploy/make_pdfs.py
"""
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "18.05-spring-2022" / "static_resources"
DST = ROOT / "deploy" / "pdfs"

con = sqlite3.connect(ROOT / "data" / "bruinbuddy.db")
public = [r[0] for r in con.execute("SELECT file_name FROM documents WHERE tutor_only=0")]
secret = {r[0] for r in con.execute("SELECT file_name FROM documents WHERE tutor_only=1")}
assert public and not (set(public) & secret), "a file is both public and tutor-only"

shutil.rmtree(DST, ignore_errors=True)
DST.mkdir(parents=True)
for name in public:
    shutil.copy2(SRC / name, DST / name)
leaked = [p.name for p in DST.iterdir() if p.name in secret or "_sol" in p.name]
if leaked:
    sys.exit(f"refusing: solution files in deploy/pdfs: {leaked}")
print(f"copied {len(public)} public PDFs ({sum(p.stat().st_size for p in DST.iterdir()) / 1e6:.1f} MB) to {DST}")
