# Memory — `qa-security-auditor`

*Last updated: 2026-10-20*

## 1. Test Suite Architecture (`backend/tests/`)
- **Command:** `cd backend && ../backend/.venv/bin/python -m pytest -q`
- **Current Baseline:** 98 passing tests using `BB_MOCK_LLM=1` and a temporary SQLite database (or throw-away Postgres when `TEST_DATABASE_URL` is set). Zero external API keys required.
- **Key Test Files:**
  - `conftest.py` — Fixtures for synthetic courses, owners, staff, students, materials, problem sets, solutions, and mock LLM responses.
  - `test_hardening.py` — Regressions for security boundaries, tenancy enforcement (`404` vs `403`), solution protection, payment verification (`_pays_for`), and SQL portability.
  - `test_tutor.py` — Graded/Practice/Solutions-open mode behavior, attempt checking, leak guard buffering, and citation scoping.
  - `test_materials.py` — Uploads, extraction, linking/unlinking problem sets and solutions, mismatch warnings.
  - `test_courses.py`, `test_accounts.py`, `test_dashboard.py`, `test_platform.py` — Auth, course lifecycle, allowances, pauses, small-group dashboard privacy, and billing.

## 2. Mandatory Regression Policy
- Every bug fix must include a regression test that fails without the fix and passes with it.
- Every new route must be tested for non-member (`404`), removed/blocked member (`403`), and student vs. staff role separation.
