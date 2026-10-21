"""Course materials (PRD §3.2): upload by category, background processing, mismatch warnings, the staff library,
problem set modes, and the student "Browse materials" list.

The category a person picks is the safety decision. The mismatch check only ever adds a warning."""
import hashlib
import json
import re
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from . import auth, config, jobs, knowledge, llm, starters, storage
from .courses import Member, get_member, get_staff
from .db import db, now
from .extract import NoText, chunk_pages, extract_pages
from .knowledge import KINDS, KIND_LABELS, MODE_LABELS, MODES, bump_content, natural_key

router = APIRouter()

TYPES = {".pdf": "application/pdf", ".txt": "text/plain", ".md": "text/markdown"}

MISMATCH_SYSTEM = """You check whether an uploaded course file matches the category a professor chose. Categories: lecture_notes, reading, class_prep, problem_set, solution, other. A "solution" contains worked answers to problems; a "problem_set" poses problems without answers.
Given the file name, the chosen category and the start of its text, reply with JSON only: {"category": "<the category it most looks like>", "confident": true | false}"""


def _ext(name: str) -> str:
    m = re.search(r"\.[A-Za-z0-9]+$", name or "")
    return m.group(0).lower() if m else ""


def _title(name: str) -> str:
    stem = re.sub(r"\.[A-Za-z0-9]+$", "", name).strip()
    return (stem or "Untitled")[:200]


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)[-120:] or "file"


def file_url(doc_id: str, page: int | None = None, staff: bool = False) -> str:
    return f"/files/{doc_id}?t={auth.make_file_token(doc_id, staff=staff)}" + (f"#page={page}" if page else "")


# ---- processing ------------------------------------------------------------------------------------
def _heuristic_warning(file_name: str, kind: str, text: str) -> str | None:
    name = file_name.lower()
    looks_solution = bool(re.search(r"(^|[^a-z])(sol|soln|solns|solutions?|answers?|answer[ _-]?key)([^a-z]|$)", name)) \
        or len(re.findall(r"\bsolutions?\b", text[:3000], re.I)) >= 2
    if looks_solution and kind != "solution":
        return f"This looks like a solution but is tagged as {KIND_LABELS[kind].lower()}."
    return None


def _model_warning(file_name: str, kind: str, text: str, course_id: int) -> str | None:
    raw = llm.complete("mismatch", [{"role": "system", "content": MISMATCH_SYSTEM},
                                    {"role": "user", "content": f"FILE NAME: {file_name}\nCHOSEN CATEGORY: {kind}\n\n"
                                                                f"TEXT:\n{text[:2000]}"}],
                       max_tokens=60, attr={"course_id": course_id})
    out = llm.parse_json(raw)
    guess = out.get("category")
    if out.get("confident") and guess in KINDS and guess != kind:
        if {guess, kind} <= {"lecture_notes", "reading", "class_prep", "other"}:
            return None  # mixing up public categories doesn't matter for safety
        return f"This looks like {KIND_LABELS[guess].lower()} but is tagged as {KIND_LABELS[kind].lower()}."
    return None


def _set_status(doc_id: str, status: str, detail: str | None = None) -> None:
    with db() as conn:
        conn.execute("UPDATE documents SET status=?, status_detail=?, updated_at=? WHERE id=?",
                     (status, detail, now(), doc_id))


def process_document(doc_id: str, data: bytes | None = None) -> None:
    """Extract, chunk and index one uploaded document. Runs in the background."""
    with db() as conn:
        doc = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not doc:
        return
    try:
        if data is None:
            data = storage.get(doc["storage_path"])
        pages = extract_pages(data, doc["file_name"])
        chunks = chunk_pages(pages)
        if not chunks:
            raise NoText()
    except NoText:
        _set_status(doc_id, "no_text", "No text found. Scanned PDFs aren't supported; upload a PDF with selectable text.")
        return
    except storage.NotFound:
        _set_status(doc_id, "failed", "The original file is missing. Upload it again.")
        return
    except Exception as e:  # corrupt or encrypted files
        _set_status(doc_id, "failed", f"Couldn't read this file ({type(e).__name__}). Check that it opens, then retry.")
        return
    with db() as conn:
        used = conn.execute("SELECT COALESCE(SUM(pages),0) AS n FROM documents WHERE course_id=? AND status='ready' "
                            "AND id<>?", (doc["course_id"], doc_id)).fetchone()["n"]
        if used + len(pages) > config.MAX_PAGES_PER_COURSE:
            conn.execute("UPDATE documents SET status='failed', status_detail=? WHERE id=?",
                         (f"This course has reached its limit of {config.MAX_PAGES_PER_COURSE:,} pages.", doc_id))
            return
        conn.execute("DELETE FROM chunks WHERE doc_id=?", (doc_id,))
        for page, text in chunks:
            conn.execute("INSERT INTO chunks(doc_id,page,text,tutor_only) VALUES(?,?,?,?)",
                         (doc_id, page, text, int(doc["kind"] == "solution")))
        conn.execute("UPDATE documents SET status='ready', status_detail=NULL, pages=?, file_hash=?, warning=NULL, "
                     "updated_at=? WHERE id=?", (len(pages), hashlib.sha256(data).hexdigest(), now(), doc_id))
        bump_content(conn, doc["course_id"])
    text = "\n".join(t for _, t in pages[:3])
    warning = _heuristic_warning(doc["file_name"], doc["kind"], text)
    if warning is None:
        try:
            warning = _model_warning(doc["file_name"], doc["kind"], text, doc["course_id"])
        except Exception:
            warning = None  # the check is advisory; a failure adds no warning
    if warning:
        with db() as conn:
            conn.execute("UPDATE documents SET warning=? WHERE id=?", (warning, doc_id))
    with db() as conn:
        c = conn.execute("SELECT content_version, starter_version FROM courses WHERE id=?", (doc["course_id"],)).fetchone()
    starters.ensure(doc["course_id"], c["content_version"], c["starter_version"])


def recover_interrupted() -> None:
    """On startup: documents left 'processing' by a restart can be retried from their stored original."""
    with db() as conn:
        conn.execute("UPDATE documents SET status='failed', status_detail=? WHERE status='processing'",
                     ("Processing was interrupted. Click Retry.",))


# ---- upload --------------------------------------------------------------------------------------------
def _course_psets(conn, course_id: int) -> set[str]:
    return {r["id"] for r in conn.execute("SELECT id FROM documents WHERE course_id=? AND kind='problem_set'",
                                          (course_id,)).fetchall()}


def _parse_ids(raw: str) -> list[str]:
    raw = (raw or "").strip()
    if not raw:
        return []
    try:
        ids = json.loads(raw) if raw.startswith("[") else raw.split(",")
    except json.JSONDecodeError:
        raise HTTPException(422, "Invalid problem set list")
    return [str(i).strip() for i in ids if str(i).strip()]


def _read_upload(f: UploadFile) -> tuple[bytes, str]:
    ext = _ext(f.filename or "")
    if ext not in TYPES:
        raise HTTPException(422, f"{f.filename}: only PDF, .txt and .md files are supported.")
    data = f.file.read(config.MAX_UPLOAD_BYTES + 1)
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"{f.filename} is larger than {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    if not data:
        raise HTTPException(422, f"{f.filename} is empty.")
    return data, ext


@router.post("/api/courses/{course_id}/materials")
def upload(kind: str = Form(...), rights: bool = Form(False), pset_ids: str = Form(""),
           files: list[UploadFile] = File(...), m: Member = Depends(get_staff)):
    cid = m.course["id"]
    if kind not in KINDS:
        raise HTTPException(422, "Pick a category first.")
    if not rights:
        raise HTTPException(422, "Confirm that you have the right to use these materials.")
    if not files or len(files) > config.MAX_FILES_PER_UPLOAD:
        raise HTTPException(422, f"Upload between 1 and {config.MAX_FILES_PER_UPLOAD} files at a time.")
    links = _parse_ids(pset_ids) if kind == "solution" else []
    payloads = [(f.filename or "file", *_read_upload(f)) for f in files]  # validate everything before saving anything
    with db() as conn:
        if links and not set(links) <= _course_psets(conn, cid):
            raise HTTPException(422, "A selected problem set isn't in this course.")
        count = conn.execute("SELECT COUNT(*) AS n FROM documents WHERE course_id=?", (cid,)).fetchone()["n"]
    if count + len(payloads) > config.MAX_FILES_PER_COURSE:
        raise HTTPException(409, f"This course can hold at most {config.MAX_FILES_PER_COURSE} files.")
    created = []
    for name, data, ext in payloads:
        doc_id = uuid.uuid4().hex
        path = f"courses/{cid}/{doc_id}/{_safe_name(name)}"
        try:
            storage.put(path, data, TYPES[ext])
        except Exception:
            raise HTTPException(502, "File storage is unavailable. Please try again.")
        with db() as conn:
            conn.execute(
                "INSERT INTO documents(id,course_id,title,kind,file_name,file_hash,tutor_only,status,storage_path,"
                "content_type,size_bytes,rights_confirmed,mode,uploaded_by,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (doc_id, cid, _title(name), kind, name, hashlib.sha256(data).hexdigest(), int(kind == "solution"),
                 "processing", path, TYPES[ext], len(data), 1, "graded", m.user["id"], now(), now()))
            for pid in links:
                conn.execute("INSERT INTO solution_links(solution_id,pset_id) VALUES(?,?) ON CONFLICT DO NOTHING",
                             (doc_id, pid))
        jobs.run(process_document, doc_id, data)
        created.append({"id": doc_id, "title": _title(name), "kind": kind})
    return {"created": created}


# ---- library and browse ----------------------------------------------------------------------------
def _links(conn, course_id: int) -> tuple[dict, dict]:
    sol_to_psets: dict[str, list[str]] = {}
    pset_to_sols: dict[str, list[str]] = {}
    for r in conn.execute("SELECT l.solution_id, l.pset_id FROM solution_links l JOIN documents d ON d.id=l.solution_id "
                          "WHERE d.course_id=?", (course_id,)).fetchall():
        sol_to_psets.setdefault(r["solution_id"], []).append(r["pset_id"])
        pset_to_sols.setdefault(r["pset_id"], []).append(r["solution_id"])
    return sol_to_psets, pset_to_sols


@router.get("/api/courses/{course_id}/materials")
def list_materials(m: Member = Depends(get_member)):
    cid = m.course["id"]
    kb = knowledge.cache.get(cid)
    if not m.is_staff:  # students: what they may open, with each problem set's mode
        docs = sorted((d for d in kb.docs.values() if kb.is_public(d.id)), key=lambda d: natural_key(d.title))
        return {"materials": [{"id": d.id, "title": d.title, "kind": d.kind, "kind_label": KIND_LABELS[d.kind],
                               "url": file_url(d.id),
                               **({"mode": d.mode, "mode_label": MODE_LABELS[d.mode]} if d.kind == "problem_set" else {})}
                              for d in docs]}
    with db() as conn:
        rows = conn.execute("SELECT id, title, kind, file_name, status, status_detail, warning, pages, size_bytes, mode, "
                            "release_at, confirm_answers, created_at FROM documents WHERE course_id=?", (cid,)).fetchall()
        sol_to_psets, pset_to_sols = _links(conn, cid)
    titles = {r["id"]: r["title"] for r in rows}
    out = []
    for r in sorted(rows, key=lambda r: natural_key(r["title"])):
        item = {**dict(r), "kind_label": KIND_LABELS.get(r["kind"], r["kind"]), "confirm_answers": bool(r["confirm_answers"]),
                "public": kb.is_public(r["id"]), "url": file_url(r["id"], staff=True)}
        if r["kind"] == "problem_set":
            item["effective_mode"] = knowledge.effective_mode(r["mode"], r["release_at"])
            item["mode_label"] = MODE_LABELS[item["effective_mode"]]
            item["solutions"] = [{"id": s, "title": titles.get(s, "")} for s in pset_to_sols.get(r["id"], [])]
        if r["kind"] == "solution":
            item["psets"] = [{"id": p, "title": titles.get(p, "")} for p in sol_to_psets.get(r["id"], [])]
        out.append(item)
    return {"materials": out, "limits": {"files": config.MAX_FILES_PER_COURSE, "pages": config.MAX_PAGES_PER_COURSE,
                                         "max_mb": config.MAX_UPLOAD_BYTES // (1024 * 1024)}}


def _staff_doc(conn, course_id: int, doc_id: str):
    doc = conn.execute("SELECT * FROM documents WHERE id=? AND course_id=?", (doc_id, course_id)).fetchone()
    if not doc:
        raise HTTPException(404, "Material not found")
    return doc


class MaterialUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    kind: str | None = None
    pset_ids: list[str] | None = None        # solutions: the problem sets this file covers
    mode: str | None = None                  # problem sets
    release_at: float | None = None          # problem sets; null clears
    confirm_answers: bool | None = None      # problem sets


@router.patch("/api/courses/{course_id}/materials/{doc_id}")
def update_material(doc_id: str, body: MaterialUpdate, m: Member = Depends(get_staff)):
    cid = m.course["id"]
    given = body.model_fields_set
    with db() as conn:
        doc = _staff_doc(conn, cid, doc_id)
        kind = body.kind or doc["kind"]
        if kind not in KINDS:
            raise HTTPException(422, "Unknown category")
        if body.title is not None:
            conn.execute("UPDATE documents SET title=? WHERE id=?", (body.title.strip(), doc_id))
        if kind != doc["kind"]:
            conn.execute("UPDATE documents SET kind=?, tutor_only=?, warning=NULL WHERE id=?",
                         (kind, int(kind == "solution"), doc_id))
            conn.execute("UPDATE chunks SET tutor_only=? WHERE doc_id=?", (int(kind == "solution"), doc_id))
            if doc["kind"] == "solution":
                conn.execute("DELETE FROM solution_links WHERE solution_id=?", (doc_id,))
            if doc["kind"] == "problem_set":
                conn.execute("DELETE FROM solution_links WHERE pset_id=?", (doc_id,))
            if kind == "problem_set":
                conn.execute("UPDATE documents SET mode='graded', release_at=NULL, confirm_answers=0 WHERE id=?", (doc_id,))
        if body.pset_ids is not None:
            if kind != "solution":
                raise HTTPException(422, "Only solutions are linked to problem sets.")
            if not set(body.pset_ids) <= _course_psets(conn, cid):
                raise HTTPException(422, "A selected problem set isn't in this course.")
            conn.execute("DELETE FROM solution_links WHERE solution_id=?", (doc_id,))
            for pid in set(body.pset_ids):
                conn.execute("INSERT INTO solution_links(solution_id,pset_id) VALUES(?,?)", (doc_id, pid))
        if given & {"mode", "release_at", "confirm_answers"} and kind != "problem_set":
            raise HTTPException(422, "Only problem sets have a mode.")
        if body.mode is not None:
            if body.mode not in MODES:
                raise HTTPException(422, "Mode must be graded, practice or open.")
            conn.execute("UPDATE documents SET mode=? WHERE id=?", (body.mode, doc_id))
        if "release_at" in given:
            conn.execute("UPDATE documents SET release_at=? WHERE id=?", (body.release_at, doc_id))
        if body.confirm_answers is not None:
            conn.execute("UPDATE documents SET confirm_answers=? WHERE id=?", (int(body.confirm_answers), doc_id))
        conn.execute("UPDATE documents SET updated_at=? WHERE id=?", (now(), doc_id))
        bump_content(conn, cid)
    return {"ok": True}


@router.post("/api/courses/{course_id}/materials/{doc_id}/file")
def replace_file(doc_id: str, file: UploadFile = File(...), m: Member = Depends(get_staff)):
    cid = m.course["id"]
    data, ext = _read_upload(file)
    with db() as conn:
        doc = _staff_doc(conn, cid, doc_id)
    path = f"courses/{cid}/{doc_id}/{_safe_name(file.filename or 'file')}"
    try:
        storage.put(path, data, TYPES[ext])
    except Exception:
        raise HTTPException(502, "File storage is unavailable. Please try again.")
    if doc["storage_path"] and doc["storage_path"] != path:
        storage.delete(doc["storage_path"])
    with db() as conn:
        conn.execute("UPDATE documents SET file_name=?, storage_path=?, content_type=?, size_bytes=?, status='processing', "
                     "status_detail=NULL, warning=NULL, updated_at=? WHERE id=?",
                     (file.filename or "file", path, TYPES[ext], len(data), now(), doc_id))
        bump_content(conn, cid)  # the old text leaves the index until the new file is ready
    jobs.run(process_document, doc_id, data)
    return {"ok": True}


@router.post("/api/courses/{course_id}/materials/{doc_id}/retry")
def retry(doc_id: str, m: Member = Depends(get_staff)):
    with db() as conn:
        doc = _staff_doc(conn, m.course["id"], doc_id)
        if not doc["storage_path"]:
            raise HTTPException(409, "This material was loaded by a script and can't be reprocessed here.")
        conn.execute("UPDATE documents SET status='processing', status_detail=NULL WHERE id=?", (doc_id,))
    jobs.run(process_document, doc_id)
    return {"ok": True}


@router.delete("/api/courses/{course_id}/materials/{doc_id}")
def delete_material(doc_id: str, m: Member = Depends(get_staff)):
    cid = m.course["id"]
    with db() as conn:
        doc = _staff_doc(conn, cid, doc_id)
        conn.execute("DELETE FROM chunks WHERE doc_id=?", (doc_id,))
        conn.execute("DELETE FROM solution_links WHERE solution_id=? OR pset_id=?", (doc_id, doc_id))
        conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        bump_content(conn, cid)
    if doc["storage_path"]:
        storage.delete(doc["storage_path"])
    return {"ok": True}
