# Memory — `backend-architect`

*Last updated: 2026-10-20*

## 1. Core Backend Architecture (`backend/app/`)
- **Entrypoint:** `main.py` mounts API routers and serves static frontend assets from `frontend/dist` when built.
- **Auth (`accounts.py`, `auth.py`):**
  - Dual-mode: In production (`AUTH_PROVIDER=supabase`), verifies Supabase JWTs via JWKS and requires `SUPABASE_ANON_KEY`. Locally (`AUTH_PROVIDER` empty), uses local email/password accounts stored in SQLite.
  - Mints short-lived signed tokens for `/files` access (`public` scope for students, `staff` scope for staff).
- **Multi-Tenancy (`courses.py`, `members.py`):**
  - Dependencies: `get_member`, `get_staff`, `get_owner`.
  - Non-members receive HTTP `404` (prevents course enumeration); removed or blocked members receive HTTP `403`.
  - Roles (`owner`, `staff`, `student`) are read exclusively from the `memberships` table.
- **Billing (`billing.py`):**
  - Course activation happens *only* in `billing._activate` after either the signed Stripe webhook (`/api/stripe/webhook`) or server-side session verification passes `_pays_for` (checks metadata, paid state, and full USD price).
  - Local dev test checkout is only enabled when Stripe keys are unset and outside production.
- **Database (`db.py`):**
  - Uses `?` placeholders everywhere; `db.py` translates `?` to `%s` (and escapes literal `%`) when connected to Postgres (`psycopg`).
  - Use `db.lock_row` before seat-count checks or other count-then-insert operations to prevent race conditions.
  - Avoid SQLite-only functions (`group_concat`, etc.).
- **Pre-Turn Gates (`chats.py`):**
  - `chats.post_message` checks course pause windows, per-student token allowances, course AI budget, and app-wide limits *before* invoking `tutor.run_turn`.
