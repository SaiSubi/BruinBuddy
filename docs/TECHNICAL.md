# BruinBuddy — Technical Architecture (v1)

> Status: v1, being built on branch `v1-build` | Based on [PRD.md](PRD.md) (v1) and [DESIGN.md](DESIGN.md) | Last updated: 2026-10-20
> v0 is described in [PRD_v0.md](PRD_v0.md) and in this file's git history. Model choice and prompts are in [AI_STRATEGY.md](AI_STRATEGY.md).
> Where the PRD leaves a question open, this file records the default the build uses and marks it **(build default)** so it can be changed later.

## 1. System overview
```
                    ┌──────────── Supabase Auth (email + password, Google, password reset)
                    │  sign-up / login in the browser, returns a JWT
Browser (React SPA) ┤
                    │  HTTPS + SSE, Authorization: Bearer <JWT>
                    ▼
Backend (FastAPI, Python)
   ├─ Accounts: verify the JWT (Supabase JWKS), map it to a user row
   ├─ Courses: memberships and roles, student code, staff codes, roster, settings, pause windows
   ├─ Billing ──────────────► Stripe Checkout (test mode) ──► webhook back to /api/stripe/webhook
   ├─ Materials: upload → background job (extract, chunk, mismatch check) ──► Supabase Storage
   ├─ Knowledge: one BM25 index + leak guard per course, rebuilt when materials or modes change
   ├─ Chat API ──► Tutor pipeline ──► OpenRouter (tutor, checker, helpers)
   ├─ Memory worker (per course) ──► OpenRouter (cheap model)
   └─ Dashboard API (aggregates only)
Database: Postgres on Supabase in production, SQLite locally (same SQL)
Files: private Supabase Storage bucket in production, data/uploads locally
```
Everything is one FastAPI service, as in v0. Each course is a tenant: every query below is scoped by `course_id`, and every route checks the caller's membership in that course.

## 2. Stack changes from v0
| Area | v1 choice | Why |
|---|---|---|
| Sign-up and login | **Supabase Auth** in the browser (`@supabase/supabase-js`, PKCE flow). The backend verifies the access token against the project's public JWKS (ES256) with PyJWT. | Same Supabase project we already use. No auth secrets on our server, and Google sign-in and password reset come built in. |
| Local development auth | A small email + password provider in the backend (`AUTH_PROVIDER=local`): scrypt password hashes and HMAC session tokens. Refused in production. | Lets the app and the test suite run with no Supabase project. |
| Payments | **Stripe Checkout** (test mode) with inline `price_data`, plus a signed webhook. `stripe` Python SDK. | Hosted payment page; no card data touches our servers. |
| Uploads | `python-multipart` for uploads; PyMuPDF moves into the runtime image for PDF text extraction. | Professors upload their own materials (PRD §3.2). |
| Retrieval | Still BM25 in memory, now **one index per course**, cached and rebuilt when the course's materials or problem set modes change. | Free, fast, and good enough at course scale. |
| Routing (frontend) | A tiny hash router (`#/c/12/staff/materials`). | Works on Vercel and when the backend serves the build, with no rewrite rules. |

Unchanged: FastAPI + React/Vite, KaTeX, OpenRouter through the `openai` SDK, SSE streaming, Postgres/SQLite with `?` placeholders, Fly.io + Vercel + Supabase.

## 3. Accounts and authentication
- **Production (`AUTH_PROVIDER=supabase`).** The browser signs up or logs in with Supabase Auth: email and password, Google (if enabled in Supabase), and password reset by email. It sends the Supabase access token to our API as a bearer token. The backend verifies it locally: ES256 signature against `${SUPABASE_URL}/auth/v1/.well-known/jwks.json` (cached), `aud = authenticated`, issuer, expiry. It then upserts a `users` row keyed by the token's `sub`, storing email and display name. No call to Supabase per request.
- **The frontend reads the Supabase URL and the public anon key from `GET /api/config`**, so the anon key is configured once, as a backend setting, rather than baked into the Vercel build. The anon key is public by design; all our tables have row-level security on with no policies, so it cannot read them.
- **Local (`AUTH_PROVIDER=local`, the default when Supabase is not configured).** `POST /api/auth/signup` and `/api/auth/login` with email and password. Passwords are hashed with scrypt; the server returns an HMAC-signed session token (7 days). There is no email, so no password reset or Google in local mode. Production refuses to start with this provider.
- **Email confirmation** is a Supabase setting. For the demo it is off (Supabase's built-in sender only mails project members and is rate-limited). If sign-up returns no session, the UI says "check your email to confirm".
- **Roles come only from `memberships`** (PRD §2.1). There is no role on the user or the sign-in form. One login can own one course and be a student in another.
- The demo's name-and-access-code sign-in is removed.

## 4. Courses, membership and access codes
**Course lifecycle.** `pending` (created, not paid) → `active` (payment confirmed by Stripe). Students cannot join a pending course. The tutor answers students only when the course is active **and** has at least one ready document.

**Roles.**
| Action | Owner | Staff | Student |
|---|---|---|---|
| Materials, guidelines, problem set modes, pause windows | ✓ | ✓ | |
| Roster: view, remove, block students; rotate code; domain and expiry; token cap | ✓ | ✓ | |
| Dashboard, preview as student | ✓ | ✓ | |
| Staff codes, remove staff, billing | ✓ | | |
| Tutor chat, browse materials | preview | preview | ✓ |

**Student code (route B).** One per course, generated at creation (format `ABCD-2345`, no look-alike characters). Joining checks, in order: the code exists, the course is active, the code has not expired, the email domain matches if a restriction is set (the email's domain or any subdomain), the student is not blocked, and the seat cap. **Rotate** replaces the code; existing members keep access. A removed student can rejoin with the current code; a blocked one cannot.

**Staff codes.** Single-use, `STAFF-XXXX-XXXX-XXXX`, valid 7 days. Stored as a SHA-256 hash; the owner sees the full code once, at creation, and afterwards only its last four characters. Redeeming is one conditional `UPDATE … WHERE used_by IS NULL AND revoked_at IS NULL AND expires_at > now`, so a code works once. Active staff plus unused, unexpired codes may not exceed the plan's staff seats. The owner can revoke an unused code and remove staff.

**One code field.** Students and staff both use "Enter a course code"; the server tells them apart by the `STAFF-` prefix.

**Roster.** Name, email, joined date, questions and tokens used. Remove frees the seat at once; block also stops rejoining. Removed members lose all access to the course, including their old chats (PRD §4.12 proposal); their data is kept.

## 5. Payments
**Plan.** The owner picks student seats, staff seats, and a per-student token allowance with its period.

**Pricing (build default; PRD §2.7 is open).** One payment per course per 10-week term:
```
weekly_allowance = token_cap × {day: 7, week: 1, term: 0.1}[cap_period]
price  = $19 base
       + $9 × staff seats            (the owner is free)
       + student seats × $2 × weekly_allowance / 100,000 tokens   (at least $0.50 per seat)
course ceiling (tokens) = (student seats + staff seats + 1) × weekly_allowance × 10 weeks
```
Example: 40 students, 2 staff, 100k tokens per week → $19 + $18 + $80 = **$117**. The formula lives in one function (`billing.quote`) and `POST /api/billing/quote` returns it, so the UI never computes a price itself.

**Checkout.**
1. `POST /api/courses` creates the course as `pending` with an owner membership and the quoted price.
2. `POST /api/courses/{id}/checkout` creates a Stripe Checkout Session (`mode=payment`, inline `price_data`, `metadata.course_id`, `client_reference_id`, the owner's email) and returns its URL. The success and cancel URLs point back to the app origin the browser sent, which must be in `ALLOWED_ORIGINS`.
3. **The webhook is the source of truth.** `POST /api/stripe/webhook` verifies the `Stripe-Signature` header with `STRIPE_WEBHOOK_SECRET`, records the event id (duplicates are ignored), and on `checkout.session.completed` or `checkout.session.async_payment_succeeded` with `payment_status = paid` marks the course `active`.
4. When the browser returns from Stripe, the app calls `POST /api/courses/{id}/checkout/confirm` with the session id. The server **asks Stripe itself** (`sessions.retrieve`) and activates the course if Stripe says it is paid and the session belongs to this course. This covers a slow or misconfigured webhook. The browser's redirect alone never activates anything.
5. A cancelled or failed payment leaves the course `pending`; the owner can retry checkout.

**Without Stripe keys** (local development and tests), checkout goes to a built-in **test checkout page** served by the backend, which simulates the webhook. It is disabled in production, which refuses to start without `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET`.

Out of scope (PRD §2.8): live payments, refunds, proration, taxes, invoices, subscriptions.

## 6. Course materials
**Upload** (`POST /api/courses/{id}/materials`, multipart): one category for the batch, one or more files, the rights checkbox, and for solutions the problem sets they cover (or none, "link later").

| Category (`kind`) | Retrieval and citation |
|---|---|
| `lecture_notes`, `reading`, `class_prep`, `other` | Public, citable |
| `problem_set` | Public, citable. Has a mode (§9). |
| `solution` | Tutor-only until **all** of its linked problem sets are open. Unlinked solutions are always tutor-only. |

**Processing** runs in a background thread per upload:
1. Save the original: Supabase Storage at `courses/{course}/{doc}/{file}` in production, `data/uploads/…` locally. Insert the document as `processing`.
2. Extract text per page (PyMuPDF for PDF; UTF-8 for `.txt`/`.md`, split into ~3,000-character parts). A PDF with no extractable text becomes `no_text` ("no text found; scanned PDFs are not supported").
3. Clean and chunk exactly as in v0 (§6.1 below), store chunks, set `ready` (or `failed` with a short reason).
4. **Mismatch check** (warns only): a filename and keyword heuristic, then one cheap model call on the first ~2,000 characters asking which category the file looks like. A disagreement is stored as `warning` ("This looks like a solution but is tagged as a reading"). The category is never changed automatically.
5. Bump the course's `content_version`, so the course's index is rebuilt and its starter questions regenerate.

Documents left in `processing` by a restart are marked `failed` on startup with "processing was interrupted"; **Retry** reprocesses the stored original. **Replace** uploads a new file under the same document id. **Re-categorise** and **delete** bump `content_version`; delete removes the chunks and the stored file, so the material disappears from the tutor and from future citations.

**Caps (build default):** 300 files and 4,000 pages per course, 20 MB per file. File types: PDF, `.txt`, `.md`.

### 6.1 Text extraction and chunking (unchanged from v0)
NFKC normalisation (math-italic letters become plain letters), folding table cells that PyMuPDF emits one per line, chunks of up to ~1,400 characters that never cross a page, each keeping its page number and document.

### 6.2 The 18.05 demo course
`python -m app.ingest --owner-email <email>` creates (or updates) the demo course from the local MIT OCW export: lecture notes, readings and class prep, problem sets, and solutions linked to their problem sets by file name. It is `active` with no payment, its problem sets default to Graded, and it gets a generated student code. Solution PDFs are not uploaded to Storage (their text lives in the database only). `python -m app.seed sample-data` adds sample students and questions for the dashboard (PRD §3.6), all flagged `is_sample`.

## 7. Knowledge per course
`knowledge.py` keeps, per course, an in-memory **BM25 index of the chunks students may see** and a **leak guard** built from the solutions they may not see.

- **What is public right now:** ready documents that are not solutions, plus solutions whose linked problem sets are all open. A problem set is open when its mode is `open` or its release date has passed.
- **Cache key:** `(content_version, set of open problem sets)`. Each turn reads both with two small queries; if the key changed (an upload finished, a mode changed, a release date passed), the course's index and guard are rebuilt. This also works with more than one server process.
- **Guard:** 6-word shingles of the protected solution chunks, minus any shingle that also appears in the course's public chunks (v0 logic). Solutions linked only to Practice sets are left out of the guard, because Practice allows worked explanations.
- The checker reads protected solution chunks straight from the database (`solution_chunks_for`), never through the index.

## 8. Tutor pipeline (one student message)
0. **Gates**, in this order, each returning a clear message and making **no model call**: signed in → active member of an active course → course has a ready document → not inside a pause window (423) → student under their token allowance and the course under its ceiling (429) → app-wide daily safety limit (429). Save the question with its course, student and preview flag.
1. **Load context:** the last 8 messages of the chat and the student's memory notes **for this course** (up to 15).
2. **Which problem set applies:** the chat's attached problem set if it was opened from "Help with a problem set"; otherwise v0's detection, now per course: a reference like "pset 4", "problem set 04", "homework 3" or "class 7 problems" matched against the course's problem set titles, or at least 8 content words of which 60% appear in one problem set chunk. The previous 3 student messages are checked too.
3. **Mode** of that problem set: Graded (default), Practice or Open (§9).
4. **Rewrite the query** for short follow-ups (cheap model, as in v0).
5. **Retrieve** the top 6 public chunks of this course. Quiz chats exclude Graded problem sets. Review chats take up to 4 chunks from the chosen material and fill the rest from the whole course.
6. **Check the attempt** (Graded and Practice only): the checker sees the linked solution excerpts and returns `{attempt_status, feedback}`. The tutor never sees solution text.
7. **Build the prompt:** core rules, the mode's rules and the "tell students if their final answer is correct" setting, the chat type (quiz, review), the professor's guidelines (general, plus tagged guidelines whose material is among the retrieved sources or is the problem set), memory notes, retrieved chunks `[S1]…[S6]`, the checker's note, history.
8. **Generate.** Graded turns are buffered until the guard passes; other turns stream.
9. **Guard** (§9), then **validate citations** (drop markers that don't match a retrieved chunk), then detect **not covered**: the tutor starts such replies with `[NC]`, which is stripped; a phrase check is the fallback.
10. **Save** the reply, and tag the question with its cited documents, problem set, attempt result and not-covered flag for the dashboard.
11. **Update memory** in a background thread, scoped to the course.

## 9. Problem set modes and solution protection
| Effective mode | Tutor behaviour | Solution text | Guard |
|---|---|---|---|
| **Graded** (default) | Hints and questions only. Buffered reply. | Checker only | Text-overlap guard + model leak check; a leaking reply is replaced with a fixed safe reply |
| **Practice** | Guided help; a worked explanation after an attempt or on request | Checker only; never cited or served | Text-overlap guard against Graded solutions only |
| **Open** (mode set, or release date passed) | Full discussion | Public: retrieved, cited and served | None for this set's solutions |

- New problem sets default to Graded, so a forgotten setting fails safe. A solution linked to several sets stays protected until **all** of them are open.
- **Guidelines cannot change any of this.** They are inserted below the safety rules with an explicit note that they cannot unlock solutions, turn off citations or change modes, and the guard runs in code whatever the prompt says.
- **File serving:** `/files/{doc}` serves only documents that are public now. Staff links carry a staff scope and may open any material in their course, including solutions, for checking their library. Uploaded solutions are kept in the private bucket; the server simply never signs a student link for them until released.
- **Pause:** while a pause window is active, the chat endpoint returns 423 with the pause message and makes no model call.

## 10. Usage limits
- **Per-student allowance:** tokens (prompt + completion, all calls in the student's turns, including the background memory update) over a rolling window of the course's period (day, week or term; default week). Checked before each turn. The 429 message says when allowance frees up (the oldest usage in the window plus the period).
- **Course ceiling:** total tokens for the course, including staff preview chats and course-level helper calls (starter questions, mismatch checks). At the ceiling, students get "this course has used its plan's AI allowance".
- **App-wide safety limit:** `GLOBAL_DAILY_LIMIT` questions per rolling 24 hours across all courses (cost backstop; default 600).
- `usage_log` now records `course_id`, `user_id` and `chat_id` for every call; the background memory thread carries the same attribution.

## 11. Dashboard
`GET /api/courses/{id}/dashboard?range=7d|30d|term` (staff only). Preview chats are excluded. Nothing returns chat content except the unanswered list, which has no names and masks email addresses.

| Panel | Computed from |
|---|---|
| Usage overview | distinct active students, questions per day (browser's time zone), active student seats / seat cap, course tokens / ceiling |
| Most-asked materials | questions per cited document (from the citations of each answer) |
| Unanswered questions | questions whose answer was marked not covered (text truncated, newest first) |
| Where students are stuck | per problem set: students asking, questions per student, checker results (correct, partial, incorrect) |
| Student usage | per student: questions and tokens in the range (numbers only) |

**Small-group rule:** with fewer than 5 active students in the range, the materials, unanswered and stuck panels are hidden; a problem set row with fewer than 5 students is hidden too. Responses say when sample data is included.

## 12. Data model
| Table | Key fields |
|---|---|
| `users` | `id`, `auth_id` (Supabase `sub`, or `local:…`), `email`, `name`, `password_hash` (local only), `is_sample` |
| `courses` | `id`, `name`, `owner_id`, `status` (`pending`/`active`), plan (`student_seats`, `staff_seats`, `token_cap`, `cap_period`, `token_ceiling`, `price_cents`), access (`student_code`, `code_expires_at`, `email_domain`), `general_guideline`, `starter_questions`, `starter_version`, `content_version`, `setup` (checklist flags), `stripe_session_id`, `paid_at` |
| `memberships` | `course_id`, `user_id`, `role` (`owner`/`staff`/`student`), `status` (`active`/`removed`/`blocked`), unique per course and user |
| `staff_codes` | `course_id`, `code_hash`, `last4`, `expires_at`, `used_by`, `used_at`, `revoked_at` |
| `documents` | v0 fields + `course_id`, `status`, `status_detail`, `storage_path`, `content_type`, `pages`, `size_bytes`, `warning`, `rights_confirmed`, `mode`, `release_at`, `confirm_answers`, `uploaded_by`, timestamps |
| `solution_links` | `solution_id`, `pset_id` (one solution can cover several sets) |
| `chunks` | `id`, `doc_id`, `page`, `text`, `tutor_only` (1 for solution chunks) |
| `guidelines` | tagged guidelines: `course_id`, `text`, `doc_ids` (JSON). The general guideline is on `courses`. |
| `pauses` | `course_id`, `starts_at`, `ends_at`, `message` |
| `chats` | `course_id`, `user_id`, `title`, `kind` (`chat`/`pset`/`review`/`quiz`), `doc_id` (attached material), `is_preview` |
| `messages` | v0 fields + on questions: `course_id`, `user_id`, `is_preview`, `doc_ids` (cited, JSON), `problem_doc_id`, `attempt_status`, `not_covered`, `leak_blocked` |
| `memories` | `course_id`, `user_id`, `text` |
| `usage_log` | v0 fields + `course_id`, `user_id`, `chat_id`, `total_tokens` |
| `stripe_events` | `id` (Stripe event id), `type`, `created_at` (webhook idempotency) |

**Migration from v0.** On first start, if the v0 tables are found (`users` has a `role` column), `users`, `chats`, `messages` and `memories` are **copied** to `v0_users`, `v0_chats`, `v0_messages` and `v0_memories`, then dropped and recreated in the v1 shape, in one transaction. `documents`, `chunks` and `usage_log` are kept and get their new columns with `ALTER TABLE … ADD COLUMN`. Existing documents have no course until `python -m app.ingest` attaches them to the demo course. New columns are added idempotently on every start, so the same code runs on a fresh or an old database.

## 13. API
All routes except the public ones need `Authorization: Bearer <token>`. Course routes check an **active** membership and the role in the table in §4; a non-member gets 404 so course ids can't be probed.

| Route | Who | Purpose |
|---|---|---|
| `GET /api/health`, `GET /api/config` | public | Liveness; auth provider, Supabase URL and anon key, billing mode |
| `POST /api/auth/signup`, `POST /api/auth/login` | public, local provider only | Email + password accounts for development |
| `POST /api/stripe/webhook` | Stripe (signed) | Activate paid courses |
| `GET /files/{doc_id}?t=` | signed link | Short-lived, document-bound link; redirects to Supabase Storage in production |
| `GET /api/me` | signed in | User and course memberships |
| `POST /api/billing/quote` | signed in | Price and ceiling for a plan |
| `POST /api/courses` | signed in | Create a pending course (caller becomes owner) |
| `POST /api/join` | signed in | Join with a student or staff code |
| `GET /api/courses/{id}` | member | Course view: role, status, pause, allowance (students), starter questions, setup checklist and code (staff) |
| `PATCH /api/courses/{id}` | staff | Name, email domain, code expiry, token cap and period |
| `POST /api/courses/{id}/code/rotate` | staff | New student code |
| `POST /api/courses/{id}/setup` | staff | Mark a checklist step done |
| `POST /api/courses/{id}/checkout`, `…/checkout/confirm` | owner | Start Stripe Checkout; confirm on return |
| `GET /api/courses/{id}/materials` | member | Students: public materials with problem set modes. Staff: everything with status, warnings and links |
| `POST /api/courses/{id}/materials` | staff | Upload (multipart) |
| `PATCH /api/courses/{id}/materials/{doc}` | staff | Title, category, solution links, mode, release date, confirm-answers |
| `POST …/materials/{doc}/file`, `…/retry`, `DELETE …/materials/{doc}` | staff | Replace, retry, delete |
| `GET`, `PUT /api/courses/{id}/guidelines` | staff | General and tagged guidelines |
| `GET`, `POST /api/courses/{id}/pauses`, `DELETE …/pauses/{pid}` | staff | Pause windows |
| `GET /api/courses/{id}/members`, `POST …/members/{user}` | staff | Roster; remove, block, unblock (removing staff: owner only) |
| `GET`, `POST /api/courses/{id}/staff-codes`, `DELETE …/staff-codes/{cid}` | owner | Single-use staff codes |
| `GET /api/courses/{id}/dashboard` | staff | §11 |
| `GET`, `POST /api/courses/{id}/chats` | member | List or create the caller's chats (`kind`, `doc_id`) |
| `GET /api/chats/{id}`, `POST /api/chats/{id}/messages` | chat owner, active member | Read; send (SSE: `delta`, optional `replace`, `done` with citations and the problem set rule, or `error`) |
| `GET /api/sources/{chunk}` | member of the chunk's course | A citation's passage, only if public now |

Errors are `{detail}` with standard codes: 401 not signed in, 403 wrong role, 404 not found or not a member, 409 not ready (pending course, no materials), 413 too large, 422 invalid input, 423 paused, 429 limit reached, 502 storage or payment provider unavailable.

## 14. Security, privacy, cost
- **Tenancy:** every course query is filtered by `course_id` after a membership check; chats also check `user_id`. Sources and files re-check that the material is public at request time.
- **Auth:** Supabase JWTs verified locally (signature, audience, issuer, expiry). Local tokens are HMAC-signed. Production refuses to start with the local provider, the mock LLM, the mock checkout, a weak `SECRET_KEY`, or missing Supabase or Stripe settings.
- **Payments:** card data stays on Stripe. The webhook signature is required; events are processed once.
- **Secrets:** server-side only (Fly secrets; `.env` and `.env.production` locally, git-ignored). The browser receives only the Supabase URL and anon key (public by design).
- **Privacy:** staff see aggregates, never chats (PRD §3.6). Student messages, retrieved course text and memory notes go to OpenRouter and the model provider. Domain restriction is only meaningful when Supabase email confirmation is on.
- **Cost:** token caps per student and per course, the app-wide limit, `max_tokens` on every call, top-6 retrieval, 8 messages of history, and per-call cost in `usage_log`.
- **Licensing:** the demo course credits MIT OCW 18.05 (CC BY-NC-SA 4.0); uploads require the professor to confirm they have the right to use the materials.

## 15. Testing
- **Automated** (pytest, mock LLM, mock checkout, local auth): the suite builds its own small **synthetic course** (a few text documents: notes, a problem set and its solution) in a temporary database, so it needs neither the 18.05 export nor any key, and it runs in GitHub Actions before every deploy. It covers sign-up and login, course creation and the checkout and webhook path (with locally computed Stripe signatures), Supabase JWT verification (with a locally generated ES256 key), codes, seat caps, removal and blocking, tenancy, uploads and statuses, modes and release, solution protection, guidelines in the prompt, pause, token caps, starter questions, the dashboard rules and the v0 migration.
- **By hand**, against a running server: the PRD acceptance criteria with the real model, and the Stripe test card in a browser.
- **Not automated:** a leak-prompt set against the real model (AI_STRATEGY.md §7).

## 16. Configuration
New settings (see `.env.example` and `.env.production.example`):

| Variable | Where | Purpose |
|---|---|---|
| `AUTH_PROVIDER` | backend | `supabase` (production) or `local` |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | backend | Auth: JWKS and issuer; anon key handed to the browser |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | backend | Checkout and webhook (test-mode keys) |
| `APP_URL` | backend | Default return URL for checkout |
| `GLOBAL_DAILY_LIMIT` | backend | App-wide question limit (cost backstop) |

## 17. Production deployment
Same layout as v0: Vercel (frontend, builds from `main`), Fly.io (backend, GitHub Actions on `main`), Supabase (Postgres, Storage, now Auth). See the README for the v1 go-live checklist: Supabase Auth settings, Stripe keys and webhook endpoint, new Fly secrets, the demo course owner, and the first-start migration.

**CI:** the deploy workflow now runs the test suite before `flyctl deploy`.

## 18. Decisions and open questions
| Decision | Choice | Alternative |
|---|---|---|
| Auth | Supabase Auth in the browser; backend verifies JWTs with JWKS | Proxy auth through our backend (shares one IP for Supabase rate limits) |
| Roles | Course memberships in our database | Roles in Supabase user metadata |
| Payment confirmation | Signed webhook, plus a server-side `retrieve` on return | Trust the success redirect |
| Price | One payment per term, formula in §5 **(build default)** | Subscription or flat tiers |
| Cap period | Rolling week **(build default)**, configurable per course | Per day or per term only |
| Per-course retrieval | Separate in-memory BM25 per course, cache keyed by content version and open sets | A shared index filtered per query; embeddings |
| Solution release | Public only when all linked sets are open | Any linked set open |
| Not-covered signal | `[NC]` marker from the tutor, phrase fallback | A separate classifier call per turn |
| Uploads processing | Background thread in the API process | A job queue and worker |

**Open questions**
- Pricing, cap period, retention and what happens when a term ends (PRD §2.7).
- Background processing in the web process can be interrupted by a scale-to-zero stop; a real job queue is the upgrade if uploads grow.
- BM25 still struggles with single-term questions; hybrid or embedding retrieval remains the main quality upgrade.
- PyMuPDF flattens math; LaTeX-aware or page-image extraction is still open.
