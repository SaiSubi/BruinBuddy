"""Ingest 18.05 PDFs into SQLite.  Run:  python -m app.ingest

Public (citable): lecture notes, readings (incl. class prep), problem sets.
Tutor-only: problem set solutions.  Everything else is skipped.
"""
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter

import pymupdf

from .config import META_DIR, PDF_DIR
from .db import db, init_db

CHUNK_TARGET = 1400  # characters, roughly 350 tokens
CHUNK_MIN = 200
INCLUDED_TYPES = {"Lecture Notes", "Readings", "Problem Sets"}


def classify(types: list[str], file_name: str) -> tuple[str | None, bool]:
    """Return (kind, tutor_only) or (None, False) if the file is not ingested."""
    t = set(types)
    is_solution = "Problem Set Solutions" in t or re.search(r"_sol\b|_sol\.", file_name) is not None
    if "Exam Solutions" in t or "Exams" in t or "Supplemental Exam Materials" in t:
        return None, False
    if is_solution and "Problem Sets" in t:
        return "problem_set_solution", True
    if not (t & INCLUDED_TYPES):
        return None, False
    if "Lecture Notes" in t:
        return "lecture_notes", False
    if "Readings" in t:
        return ("class_prep" if "prep" in file_name else "reading"), False
    return "problem_set", False


def clean_text(text: str) -> str:
    """NFKC-normalise (turns math-italic letters into plain ones) and fold table cells
    that PyMuPDF emits one per line back into a single line, to save tokens."""
    text = unicodedata.normalize("NFKC", text).replace("\u00a0", " ")
    out, run = [], []
    for line in text.split("\n"):
        line = line.strip()
        if 0 < len(line) <= 8:
            run.append(line)
            continue
        if run:
            out.append(" ".join(run))
            run = []
        if line:
            out.append(line)
    if run:
        out.append(" ".join(run))
    return "\n".join(out)


def split_page(text: str) -> list[str]:
    text = re.sub(r"[ \t]+\n", "\n", clean_text(text)).strip()
    if len(text) <= CHUNK_TARGET:
        return [text] if len(text) >= 40 else []
    paras = re.split(r"\n\s*\n", text)
    chunks, cur = [], ""
    for p in paras:
        if cur and len(cur) + len(p) > CHUNK_TARGET:
            chunks.append(cur.strip())
            cur = ""
        while len(p) > CHUNK_TARGET * 1.5:  # very long paragraph: hard split on whitespace
            cut = p.rfind(" ", 0, CHUNK_TARGET)
            cut = cut if cut > CHUNK_MIN else CHUNK_TARGET
            chunks.append((cur + "\n\n" + p[:cut]).strip() if cur else p[:cut].strip())
            cur, p = "", p[cut:].lstrip()
        cur = (cur + "\n\n" + p) if cur else p
    if cur.strip():
        if chunks and len(cur) < CHUNK_MIN:
            chunks[-1] += "\n\n" + cur.strip()
        else:
            chunks.append(cur.strip())
    return [c for c in chunks if len(c) >= 40]


def link_key(file_name: str) -> str:
    return re.sub(r"_sol(?=\.)", "", file_name)


def main() -> int:
    init_db()
    report, skipped, weak = Counter(), Counter(), []
    docs = []
    for meta_path in sorted(META_DIR.glob("*/data.json")):
        d = json.loads(meta_path.read_text())
        f = d.get("file") or ""
        if not f.lower().endswith(".pdf"):
            continue
        file_name = f.rsplit("/", 1)[-1]
        kind, tutor_only = classify(d.get("learning_resource_types", []), file_name)
        if d["title"].startswith("All "):  # compiled readings duplicate the individual readings
            kind = None
        if kind is None:
            skipped[tuple(d.get("learning_resource_types", [])) or ("untyped",)] += 1
            continue
        pdf = PDF_DIR / file_name
        if not pdf.exists():
            print(f"missing PDF: {file_name}", file=sys.stderr)
            continue
        docs.append((d["uid"], d["title"], kind, file_name, tutor_only, pdf, d.get("license", "")))

    by_link = {link_key(fn): uid for uid, _, k, fn, to, _, _ in docs if not to}
    with db() as conn:
        for uid, title, kind, file_name, tutor_only, pdf, lic in docs:
            h = hashlib.sha256(pdf.read_bytes()).hexdigest()
            row = conn.execute("SELECT file_hash FROM documents WHERE id=?", (uid,)).fetchone()
            linked = by_link.get(link_key(file_name)) if tutor_only else None
            if row and row["file_hash"] == h:
                conn.execute("UPDATE documents SET tutor_only=?, linked_doc_id=?, kind=? WHERE id=?",
                             (int(tutor_only), linked, kind, uid))
                report["unchanged"] += 1
                continue
            conn.execute("DELETE FROM chunks WHERE doc_id=?", (uid,))
            conn.execute(
                "INSERT INTO documents(id,title,kind,file_name,file_hash,tutor_only,linked_doc_id,license)"
                " VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title, kind=excluded.kind,"
                " file_name=excluded.file_name, file_hash=excluded.file_hash, tutor_only=excluded.tutor_only,"
                " linked_doc_id=excluded.linked_doc_id, license=excluded.license",
                (uid, title, kind, file_name, h, int(tutor_only), linked, lic))
            n_chunks = 0
            with pymupdf.open(pdf) as doc:
                for pno, page in enumerate(doc, start=1):
                    text = page.get_text("text")
                    if len(text.strip()) < 40:
                        weak.append(f"{file_name} p.{pno}")
                        continue
                    for c in split_page(text):
                        conn.execute("INSERT INTO chunks(doc_id,page,text,tutor_only) VALUES(?,?,?,?)",
                                     (uid, pno, c, int(tutor_only)))
                        n_chunks += 1
            report[f"ingested:{kind}"] += 1
            report["chunks"] += n_chunks

        unmatched = [r["title"] for r in conn.execute(
            "SELECT title FROM documents WHERE tutor_only=1 AND linked_doc_id IS NULL")]
        totals = {r["tutor_only"]: r["n"] for r in conn.execute(
            "SELECT tutor_only, COUNT(*) AS n FROM chunks GROUP BY tutor_only")}

    print("== Ingestion report ==")
    for k, v in sorted(report.items()):
        print(f"  {k}: {v}")
    print(f"  chunks in DB  public={totals.get(0, 0)}  tutor-only={totals.get(1, 0)}")
    print(f"  skipped (not in v0 scope): {dict(skipped)}")
    print(f"  pages with little/no text: {len(weak)} {weak[:8]}")
    print(f"  solutions without a linked problem set: {unmatched}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
