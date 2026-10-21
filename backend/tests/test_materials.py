"""Uploads, processing status, mismatch warnings, solution links and the library (PRD §3.2)."""
import pymupdf
from fastapi.testclient import TestClient

from app import config
from conftest import NOTES, PSET1, SOL1, create_course, new_user, setup_course, student_in, upload, upload_ok


def _materials(client, cid):
    return {m["id"]: m for m in client.get(f"/api/courses/{cid}/materials").json()["materials"]}


def test_upload_validation(app, monkeypatch):
    owner = new_user(app)
    cid = create_course(owner)
    assert upload(owner, cid, "lecture_notes", {"a.txt": NOTES}, rights=False).status_code == 422
    assert upload(owner, cid, "homework", {"a.txt": NOTES}).status_code == 422
    assert upload(owner, cid, "lecture_notes", {"slides.pptx": b"PK..."}).status_code == 422
    assert upload(owner, cid, "lecture_notes", {"empty.txt": b""}).status_code == 422
    monkeypatch.setattr(config, "MAX_UPLOAD_BYTES", 100)
    assert upload(owner, cid, "lecture_notes", {"big.txt": NOTES}).status_code == 413
    assert owner.get(f"/api/courses/{cid}/materials").json()["materials"] == []  # nothing half-saved


def test_upload_processes_to_ready(app):
    owner = new_user(app)
    cid = create_course(owner)
    view = owner.get(f"/api/courses/{cid}").json()
    assert not view["open"]
    doc = upload_ok(owner, cid, "lecture_notes", {"Lecture 3 - Bayes.txt": NOTES})[0]
    m = _materials(owner, cid)[doc]
    assert m["status"] == "ready" and m["pages"] == 1 and m["title"] == "Lecture 3 - Bayes" and m["public"]
    view = owner.get(f"/api/courses/{cid}").json()
    assert view["open"] and view["setup"][0] == {"step": "materials", "done": True, "detail": "1 ready, 0 processing"}


def test_scanned_and_broken_pdfs(app):
    owner = new_user(app)
    cid = create_course(owner)
    blank = pymupdf.open()
    blank.new_page()
    r = owner.post(f"/api/courses/{cid}/materials", data={"kind": "reading", "rights": "true"},
                   files=[("files", ("scan.pdf", blank.tobytes(), "application/pdf")),
                          ("files", ("broken.pdf", b"%PDF-1.4 not really a pdf", "application/pdf"))])
    assert r.status_code == 200
    statuses = {m["file_name"]: (m["status"], m["status_detail"]) for m in _materials(owner, cid).values()}
    assert statuses["scan.pdf"][0] == "no_text" and "Scanned" in statuses["scan.pdf"][1]
    assert statuses["broken.pdf"][0] == "failed"
    assert not owner.get(f"/api/courses/{cid}").json()["open"]  # failures don't open the tutor


def test_text_pdf_is_extracted(app):
    owner = new_user(app)
    cid = create_course(owner)
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Bayes theorem relates the posterior, the likelihood and the prior distribution.")
    page.insert_text((72, 100), "The law of total probability gives the normalising constant in the denominator.")
    r = owner.post(f"/api/courses/{cid}/materials", data={"kind": "lecture_notes", "rights": "true"},
                   files=[("files", ("notes.pdf", pdf.tobytes(), "application/pdf"))])
    doc = r.json()["created"][0]["id"]
    assert _materials(owner, cid)[doc]["status"] == "ready"


def test_mismatch_warning_only_warns(app):
    owner = new_user(app)
    cid = create_course(owner)
    doc = upload_ok(owner, cid, "reading", {"week5_answers.txt": SOL1})[0]
    m = _materials(owner, cid)[doc]
    assert m["kind"] == "reading" and "looks like a solution" in m["warning"]


def test_solution_links_and_student_view(app):
    owner = new_user(app)
    c = setup_course(owner)
    staff_view = _materials(owner, c["id"])
    assert staff_view[c["s1"]]["psets"] == [{"id": c["p1"], "title": "Problem Set 1"}]
    assert staff_view[c["p1"]]["solutions"][0]["id"] == c["s1"]
    assert staff_view[c["p1"]]["mode"] == "graded" and staff_view[c["p1"]]["mode_label"] == "Graded: hints only"
    assert not staff_view[c["s1"]]["public"]
    student = student_in(app, c)
    seen = _materials(student, c["id"])
    assert c["s1"] not in seen and c["s2"] not in seen and c["notes"] in seen
    assert seen[c["p1"]]["mode_label"] == "Graded: hints only"
    # an unlinked solution is protected too
    lone = upload_ok(owner, c["id"], "solution", {"Extra Solutions.txt": SOL1})[0]
    assert lone not in _materials(student, c["id"])


def test_linking_rejects_other_courses_sets(app):
    owner = new_user(app)
    a, b = setup_course(owner), create_course(owner, name="Other")
    assert upload(owner, b, "solution", {"s.txt": SOL1}, pset_ids=[a["p1"]]).status_code == 422
    assert owner.patch(f"/api/courses/{a['id']}/materials/{a['s1']}", json={"pset_ids": ["nope"]}).status_code == 422


def test_recategorise_relink_replace_delete(app):
    owner = new_user(app)
    c = setup_course(owner)
    cid = c["id"]
    student = student_in(app, c)
    # a reading re-categorised as a solution disappears for students
    assert owner.patch(f"/api/courses/{cid}/materials/{c['reading']}", json={"kind": "solution"}).status_code == 200
    assert c["reading"] not in _materials(student, cid)
    assert owner.patch(f"/api/courses/{cid}/materials/{c['reading']}", json={"kind": "reading"}).status_code == 200
    assert c["reading"] in _materials(student, cid)
    # only problem sets have modes; only solutions have links
    assert owner.patch(f"/api/courses/{cid}/materials/{c['notes']}", json={"mode": "open"}).status_code == 422
    assert owner.patch(f"/api/courses/{cid}/materials/{c['notes']}", json={"pset_ids": [c["p1"]]}).status_code == 422
    # replace: new text, reprocessed
    r = owner.post(f"/api/courses/{cid}/materials/{c['notes']}/file",
                   files={"file": ("Lecture 3 v2.txt", (NOTES + "\nA new paragraph about Markov chains.").encode())})
    assert r.status_code == 200 and _materials(owner, cid)[c["notes"]]["status"] == "ready"
    # retry reprocesses the stored original
    assert owner.post(f"/api/courses/{cid}/materials/{c['notes']}/retry").status_code == 200
    # delete
    assert owner.delete(f"/api/courses/{cid}/materials/{c['notes']}").status_code == 200
    assert c["notes"] not in _materials(owner, cid)
    assert student.delete(f"/api/courses/{cid}/materials/{c['p1']}").status_code == 403


def test_page_and_file_caps(app, monkeypatch):
    owner = new_user(app)
    cid = create_course(owner)
    monkeypatch.setattr(config, "MAX_PAGES_PER_COURSE", 1)
    upload_ok(owner, cid, "lecture_notes", {"one.txt": NOTES})
    doc = upload_ok(owner, cid, "reading", {"two.txt": PSET1})[0]
    m = _materials(owner, cid)[doc]
    assert m["status"] == "failed" and "limit" in m["status_detail"]
    monkeypatch.setattr(config, "MAX_FILES_PER_COURSE", 2)
    assert upload(owner, cid, "reading", {"three.txt": NOTES}).status_code == 409


def test_staff_file_links_open_solutions_but_student_links_do_not(app):
    owner = new_user(app)
    c = setup_course(owner)
    staff_url = _materials(owner, c["id"])[c["s1"]]["url"]
    assert TestClient(app).get(staff_url.split("#")[0]).status_code == 200
    from app.materials import file_url
    assert TestClient(app).get(file_url(c["s1"]).split("#")[0]).status_code == 404
