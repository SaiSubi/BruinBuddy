# Memory — `qa-security-auditor`

*Last updated: 2026-10-20*

## 1. Test Suite Architecture (`backend/tests/`)
- **Command:** `cd backend && ../backend/.venv/bin/python -m pytest -q`
- **Current Baseline:** 129 passing tests (incl. 4 in `test_illustrate.py`, 11 in `test_assignments.py`, 8 in `test_qna.py`) using `BB_MOCK_LLM=1` and a temporary SQLite database (or throw-away Postgres when `TEST_DATABASE_URL` is set). Zero external API keys required.
- **Key Test Files:**
  - `conftest.py` — Fixtures for synthetic courses, owners, staff, students, materials, problem sets, solutions, and mock LLM responses.
  - `test_hardening.py` — Regressions for security boundaries, tenancy enforcement (`404` vs `403`), solution protection, payment verification (`_pays_for`), and SQL portability.
  - `test_tutor.py` — Graded/Practice/Solutions-open mode behavior, attempt checking, leak guard buffering, and citation scoping.
  - `test_illustrate.py` — Skill routing (`manim_3b1b`, `anatomy_isometric`, `explainer_diagram`, `explainer_storyboard`), persistence, download formats (`html`, `svg`, `py`), tenancy (`404`), pre-turn gates (`423`, `429`), and Graded solution leak sanitization.
  - `test_materials.py`, `test_courses.py`, `test_accounts.py`, `test_dashboard.py`, `test_platform.py` — Uploads, auth, course lifecycle, allowances, pauses, small-group dashboard privacy, and billing.

## 2. Mandatory Regression Policy
- Every bug fix must include a regression test that fails without the fix and passes with it.
- Every new route must be tested for non-member (`404`), removed/blocked member (`403`), and student vs. staff role separation.
- **`test_assignments.py` (11 tests):** checkpoint drafting (staff-only, points rescaled to 100), student payloads never contain `target_answer`/`rubric`/`hint`/`solution_notes` or unreached results, tutor prompt isolation, progression and scoring, hint requests skip the verifier, skip & reveal, leak replacement and fail-closed leak check, `short_answer_leaks`, pause (423) / allowance (429), tenancy (404/403), gradebook excludes staff previews. Baseline is now 121 tests.
- **`test_qna.py` (8 tests):** extraction into pending pairs (txt + docx) and review; AI answers citing past Q&A; staff see counts only until escalation; escalation → reply → save to KB → FAQ → the next student's answer; rules (regex escalation without model calls, classifier routing, instructions placement, assistant off); pause and allowance block answers but not escalation; Graded protection and leak replacement; tenancy. Baseline is now 129 tests.
