# Memory — `backend-architect`

*Last updated: 2026-10-20*

## 1. Core Backend Architecture (`backend/app/`)
- **Entrypoint:** `main.py` mounts API routers and serves static frontend assets from `frontend/dist` when built.
- **Auth (`accounts.py`, `auth.py`):**
  - Dual-mode: In production (`AUTH_PROVIDER=supabase`), verifies Supabase JWTs via JWKS and requires `SUPABASE_ANON_KEY`. Locally (`AUTH_PROVIDER` empty), uses local email/password accounts stored in SQLite.
  - `users.account_type` (`student`/`instructor`) only gates course creation and the welcome screen, never course roles. Supabase users get it from signup metadata (default `student`); `PUT /api/me/account-type` lets a fresh account (no memberships, else 409) take the role picked before Google sign-in.
  - Mints short-lived signed tokens for `/files` access (`public` scope for students, `staff` scope for staff).
- **Multi-Tenancy (`courses.py`, `members.py`):**
  - Dependencies: `get_member`, `get_staff`, `get_owner`.
  - Non-members receive HTTP `404` (prevents course enumeration); removed or blocked members receive HTTP `403`.
  - Roles (`owner`, `staff`, `student`) are read exclusively from the `memberships` table.
- **Billing (`billing.py`):**
  - Course activation happens *only* in `billing._activate` after either the signed Stripe webhook (`/api/stripe/webhook`) or server-side session verification passes `_pays_for` (checks metadata, paid state, and full USD price).
  - Local dev test checkout is only enabled when Stripe keys are unset and outside production.
- **Database (`db.py`):**
  - Tables: `users`, `courses`, `memberships`, `staff_codes`, `documents`, `solution_links`, `chunks`, `guidelines`, `pauses`, `chats`, `messages`, `illustrations`, `memories`, `usage_log`, `stripe_events`.
  - Uses `?` placeholders everywhere; `db.py` translates `?` to `%s` (and escapes literal `%`) when connected to Postgres (`psycopg`).
  - Use `db.lock_row` before seat-count checks or other count-then-insert operations to prevent race conditions.
- **Pre-Turn Gates (`chats.py`):**
  - `chats._check_turn_gates` checks course active status, ready materials, course pause windows, per-student token allowances, course AI budget, and app-wide limits *before* invoking `tutor.run_turn` or `illustrate.generate_illustration`.
- **Illustrations (`illustrate.py`, `chats.py`):**
  - `GET /api/chats/{chat_id}/illustrations`, `POST /api/chats/{chat_id}/illustrate`, and `GET /api/illustrations/{id}/download?format=html|svg|py` all enforce `_own_chat`.
- **AI-Guided Assignments (`assignments.py`, issue #14):**
  - Tables `assignments` (checkpoints as JSON), `assignment_submissions` (unique per assignment+user, `checkpoint_states_json`, `is_preview`), `assignment_messages` (`event_type`).
  - Routes: `POST /api/courses/{id}/assignments/generate-checkpoints` and `POST /api/courses/{id}/assignments` (`get_staff`), `GET /api/courses/{id}/assignments` (`get_member`), and `/api/assignments/{aid}` (`GET`, `POST …/turn`, `POST …/skip-checkpoint`, staff-only `GET …/submissions`, `DELETE`), each resolving membership via `assignments._open` → `member_of`.
  - `_check_turn_gates(c, kb=None, …)` skips the materials check; `pause=False` only for staff drafting. Assignment user messages count toward `GLOBAL_DAILY_LIMIT`. Turn state changes run after `lock_row` on the submission and 409 if it moved meanwhile.
- **AI TA Q&A (`qna.py`, issue #20):**
  - Tables `qa_sources`, `qa_pairs` (`pending`/`approved`, `faq`, `thread_id`), `qa_threads` (`escalated` flag + status), `qa_messages` (`student`/`ai`/`staff`/`system`); rules JSON in `courses.qa_rules`.
  - Thread routes resolve access via `qna._thread_access`: the asker, or staff only when `escalated=1`; everyone else gets 404. Course routes use `get_member`/`get_staff` and filter pairs by `course_id`.
  - `_respond` order: assistant off → sensitive regex → `_check_turn_gates(c, None, …)` (a failure leaves the thread `open`) → classify → escalate or answer. Escalation has no gate. Student `qa_messages` count toward `GLOBAL_DAILY_LIMIT`. `.docx` text comes from `extract.docx_text`.
