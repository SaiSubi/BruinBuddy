# BruinBuddy — Technical Architecture (v1)

> Status: v1 live at https://bruinbuddy.vercel.app since 2026-10-20 (Vercel + Fly.io + Supabase + Stripe test mode) | Based on [PRD.md](PRD.md) (v1) and [DESIGN.md](DESIGN.md) | Last updated: 2026-10-20
> v0 is described in [PRD_v0.md](PRD_v0.md) and in this file's git history. Model choice and prompts are in [AI_STRATEGY.md](AI_STRATEGY.md).
> Choices marked **(build default)** were made during the build and have since been agreed in the PRD (§2.7, §3.10, §4.12, 2026-10-20).

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
   ├─ Knowledge: one hybrid index (BM25 + embeddings) + leak guard per course, rebuilt when materials or modes change
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
| Retrieval | **Hybrid**: BM25 plus embedding similarity, fused by reciprocal rank, in memory, **one index per course**, cached and rebuilt when the course's materials, problem set modes or embeddings change (§7.1). | BM25 alone missed paraphrased and notation-heavy questions; on 18.05 the hybrid finds a relevant chunk for 91% of labelled questions vs 83% (AI_STRATEGY.md §7). |
| Routing (frontend) | A tiny hash router (`#/c/12/staff/materials`). | Works on Vercel and when the backend serves the build, with no rewrite rules. |

Unchanged: FastAPI + React/Vite, KaTeX, OpenRouter through the `openai` SDK, SSE streaming, Postgres/SQLite with `?` placeholders, Fly.io + Vercel + Supabase.

## 3. Accounts and authentication
- **Production (`AUTH_PROVIDER=supabase`).** The browser signs up or logs in with Supabase Auth: email and password, Google (if enabled in Supabase), and password reset by email. It sends the Supabase access token to our API as a bearer token. The backend verifies it locally: ES256 signature against `${SUPABASE_URL}/auth/v1/.well-known/jwks.json` (cached), `aud = authenticated`, issuer, expiry. It then upserts a `users` row keyed by the token's `sub`, storing email and display name. No call to Supabase per request.
- **The frontend reads the Supabase URL and the public anon key from `GET /api/config`**, so the anon key is configured once, as a backend setting, rather than baked into the Vercel build. The anon key is public by design; all our tables have row-level security on with no policies, so it cannot read them.
- **Local (`AUTH_PROVIDER=local`, the default when Supabase is not configured).** `POST /api/auth/signup` and `/api/auth/login` with email and password. Passwords are hashed with scrypt; the server returns an HMAC-signed session token (7 days). There is no email, so no password reset or Google in local mode. Production refuses to start with this provider.
- **Email confirmation** is a Supabase setting. For the demo it is off (Supabase's built-in sender only mails project members and is rate-limited). If sign-up returns no session, the UI says "check your email to confirm".
- **Redirects** (Google, password reset) come back with Supabase's `?code=`, which supabase-js exchanges on start; the app only consumes its own one-time parameters (`checkout`, `reset`, sign-in errors). With the PKCE flow a password-reset link must be opened in the same browser that asked for it.
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

**Student code (route B).** One per course, generated at creation (format `ABCD-2345`, no look-alike characters). Joining checks, in order: the code exists, the course is active, the code has not expired, the email domain matches if a restriction is set (the email's domain or any subdomain), the student is not blocked, and the seat cap. The seat count and the insert run under a lock on the course row (`SELECT … FOR UPDATE` on Postgres, `BEGIN IMMEDIATE` on SQLite), so students joining at the same moment can't overfill a course; staff codes are counted the same way. **Rotate** replaces the code; existing members keep access. A removed student can rejoin with the current code; a blocked one cannot.

**Staff codes.** Single-use, `STAFF-XXXX-XXXX-XXXX`, valid 7 days. Stored as a SHA-256 hash; the owner sees the full code once, at creation, and afterwards only its last four characters. Redeeming is one conditional `UPDATE … WHERE used_by IS NULL AND revoked_at IS NULL AND expires_at > now`, so a code works once. Active staff plus unused, unexpired codes may not exceed the plan's staff seats. The owner can revoke an unused code and remove staff.

**One code field.** Students and staff both use "Enter a course code"; the server tells them apart by the `STAFF-` prefix.

**Roster.** Name, email, joined date, questions and tokens used. Remove frees the seat at once; block also stops rejoining. The owner can remove or block staff the same way (a removed but unblocked TA could otherwise rejoin as a student). Removed members lose all access to the course, including their old chats (PRD §4.12 proposal); their data is kept.

## 5. Payments
**Plan.** The owner picks student seats, staff seats, and a per-student token allowance with its period.

**Pricing (build default, agreed in PRD §2.7).** One payment per course per 10-week term:
```
weekly_allowance = token_cap × {day: 7, week: 1, term: 0.1}[cap_period]
price  = $19 base
       + $9 × staff seats            (the owner is free)
       + student seats × $2 × weekly_allowance / 100,000 tokens   (at least $0.50 per seat)
course ceiling (tokens) = (student seats + staff seats + 1) × weekly_allowance × 10 weeks
```
Example: 40 students, 2 staff, 100k tokens per week → $19 + $18 + $80 = **$117**; the course can use 43M tokens in the term. The formula lives in one function (`billing.quote`) and `POST /api/billing/quote` returns it, so the UI never computes a price itself.

**Checkout.**
1. `POST /api/courses` creates the course as `pending` with an owner membership and the quoted price.
2. `POST /api/courses/{id}/checkout` creates a Stripe Checkout Session (`mode=payment`, inline `price_data`, `metadata.course_id`, `client_reference_id`, the owner's email) and returns its URL. The success and cancel URLs point back to the app origin the browser sent; it is parsed and must be exactly an origin in `ALLOWED_ORIGINS` (or localhost in development), else `APP_URL` is used.
3. **The webhook is the source of truth.** `POST /api/stripe/webhook` verifies the `Stripe-Signature` header with `STRIPE_WEBHOOK_SECRET`, then, in one transaction, records the event id (duplicates are ignored) and on `checkout.session.completed` or `checkout.session.async_payment_succeeded` marks the course `active`, so a failure leaves the event unrecorded for Stripe's retry. A session counts as payment for a course only if it is paid, its `metadata.course_id` (set by our server) is that course, and it collected at least the course's price in USD. The payer-settable `client_reference_id` is never trusted.
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
3. Clean and chunk exactly as in v0 (§6.1 below), embed each chunk (§7.1), store chunks with their vectors, set `ready` (or `failed` with a short reason). If the embedding call fails the chunks are stored without vectors (BM25 still finds them) and the backfill fills them in later.
4. **Mismatch check** (warns only): a filename and keyword heuristic, then one cheap model call on the first ~2,000 characters asking which category the file looks like. A disagreement is stored as `warning` ("This looks like a solution but is tagged as a reading"). The category is never changed automatically.
5. Bump the course's `content_version`, so the course's index is rebuilt and its starter questions regenerate.

Documents left in `processing` by a restart are marked `failed` on startup with "processing was interrupted"; **Retry** reprocesses the stored original. **Replace** uploads a new file under the same document id. **Re-categorise** and **delete** bump `content_version`; delete removes the chunks and the stored file, so the material disappears from the tutor and from future citations.

**Caps (build default):** 300 files and 4,000 pages per course, 20 MB per file. File types: PDF, `.txt`, `.md`.

### 6.1 Text extraction and chunking (unchanged from v0)
NFKC normalisation (math-italic letters become plain letters), folding table cells that PyMuPDF emits one per line, chunks of up to ~1,400 characters that never cross a page, each keeping its page number and document.

### 6.2 The 18.05 demo course
`python -m app.ingest --owner-email <email>` creates (or updates) the demo course from the local MIT OCW export: lecture notes, readings and class prep, problem sets, and solutions linked to their problem sets by file name. It is `active` with no payment, its term is dated to have started four weeks earlier (so sample data falls inside it), its problem sets default to Graded, and it gets a generated student code. Solution PDFs are not uploaded to Storage (their text lives in the database only). `python -m app.seed sample-data` adds sample students and questions for the dashboard (PRD §3.6), all flagged `is_sample`.

## 7. Knowledge per course
`knowledge.py` keeps, per course, an in-memory **hybrid index (BM25 + chunk embeddings) of the chunks students may see** and a **leak guard** built from the solutions they may not see.

- **What is public right now:** ready documents that are not solutions, plus solutions whose linked problem sets are all open. A problem set is open when its mode is `open` or its release date has passed.
- **Cache key:** `(content_version, set of open problem sets, index_version)`. Each turn reads them with two small queries; if the key changed (an upload finished, a mode changed, a release date passed, embeddings were filled in), the course's index and guard are rebuilt. This also works with more than one server process.
- **Guard:** 6-word shingles of the protected solution chunks, minus any shingle that also appears in the course's public chunks (v0 logic). Solutions linked only to Practice sets are left out of the guard, because Practice allows worked explanations.
- The checker reads protected solution chunks straight from the database (`solution_chunks_for`), never through the index.

### 7.1 Hybrid retrieval and chunk embeddings
- **Embeddings** (`embeddings.py`): each chunk is embedded once with `EMBED_MODEL` (default `openai/text-embedding-3-small` through OpenRouter), with a short header naming its material (`Reading: Reading 3: …, p. 2`) in front of the text. The unit vector is stored on the chunk (`chunks.embedding`, float32 bytes) with the model that made it (`chunks.embed_model`); vectors from another model are ignored. Solution chunks are embedded too, so they are ready when their sets open, but like their text they only enter the index once public.
- **Backfill:** when the index is built and some ready chunks lack a current vector (data from before embeddings, a failed call, a changed model), a background job embeds them and bumps `courses.index_version`, which rebuilds the index without touching `content_version` (so starter questions aren't regenerated). It runs at most once per cache key, so an outage doesn't cause retry loops. The 18.05 seed (`app.ingest`) runs it directly.
- **Search** (`Index.retrieve`): the turn's query (after the rewrite) is embedded; BM25 hits above `MIN_RETRIEVAL_SCORE` and embedding hits above `EMBED_MIN_SIMILARITY` (cosine; 0.35, set on 18.05, where off-topic questions peaked at 0.30 and course questions started at 0.40) each contribute their top 30, fused by reciprocal rank (`1/(60 + rank)` summed). With no query vector (embedding call failed) or no chunk vectors, or when nothing clears the embedding floor, it is BM25 alone, exactly as before. Vectors are searched with a numpy dot product: about 1,100 vectors for 18.05, well under a millisecond.
- **Cost and limits:** embedding calls are logged in `usage_log` (purposes `embed`, `embed_query`) with their cost but with `total_tokens` 0, so they don't use up student allowances or the course ceiling (embedding all of 18.05 is ~500k tokens but about a cent). The query embedding adds one call of about 0.4–0.7 s per turn.
- **Tenancy:** the vectors are loaded for the same public-only chunk list as BM25, so embedding search can't return a protected solution (`tests/test_retrieval.py`).

## 8. Tutor pipeline (one student message)
0. **Gates**, in this order, each returning a clear message and making **no model call**: signed in → active member of an active course → course has a ready document → not inside a pause window (423) → student under their token allowance and the course under its ceiling (429) → app-wide daily safety limit (429). Save the question with its course, student and preview flag.
1. **Load context:** the last 8 messages of the chat and the student's memory notes **for this course** (up to 15).
2. **Which problem set applies:** the candidates are the chat's attached set (opened from "Help with a problem set"), sets the message names ("pset 4", "problem set 04", "homework 3", "class 7 problems", matched against the course's titles), and a set whose text the message pastes (at least 8 content words, 60% of them in one problem set chunk). If the message brings none, the previous 3 student messages are checked. **When several match, the strictest mode wins**, so naming a Practice or open set can't unlock a pasted Graded problem.
3. **Mode** of that problem set: Graded (default), Practice or Open (§9).
4. **Rewrite the query** for short follow-ups (cheap model, as in v0).
5. **Retrieve** the top 6 public chunks of this course with hybrid search (§7.1). Quiz chats exclude Graded problem sets. Review chats take up to 4 chunks from the chosen material and fill the rest from the whole course. When a problem set applies, up to 2 chunks come from that set, and a problem the student names ("problem 2", "question 3") brings in the chunk that states it, so hints are about the right problem even when the wording doesn't match.
6. **Check the attempt** (Graded and Practice only): the checker sees the linked solution excerpts and returns `{attempt_status, feedback}`. The tutor never sees solution text. In Practice mode the checker skips any solution file that also covers a Graded set.
7. **Build the prompt:** core rules, the mode's rules and the "tell students if their final answer is correct" setting, the chat type (quiz, review), the professor's guidelines (general, plus tagged guidelines whose material is among the retrieved sources or is the problem set), memory notes, retrieved chunks `[S1]…[S6]`, the checker's note, history.
8. **Generate.** Graded turns are buffered until the guard passes; other turns stream.
9. **Guard** (§9), then **validate citations** (drop markers that don't match a retrieved chunk), then detect **not covered**: the tutor starts such replies with `[NC]`, which is stripped; a phrase check is the fallback. Turns about a problem set are never counted as not covered: the dashboard's unanswered list is for course questions the materials don't answer.
10. **Save** the reply, and tag the question with its cited documents, problem set, attempt result and not-covered flag for the dashboard.
11. **Update memory** in a background thread, scoped to the course.

## 9. Problem set modes and solution protection
| Effective mode | Tutor behaviour | Solution text | Guard |
|---|---|---|---|
| **Graded** (default) | Hints and questions only. Buffered reply. | Checker only | Text-overlap guard + model leak check; a leaking reply is replaced with a fixed safe reply |
| **Practice** | Guided help; a worked explanation after an attempt or on request | Checker only; never cited or served | Text-overlap guard against Graded solutions only |
| **Open** (mode set, or release date passed) | Full discussion | Public: retrieved, cited and served | None for this set's solutions |

- New problem sets default to Graded, so a forgotten setting fails safe. A solution linked to several sets stays protected until **all** of them are open. Deleting or re-categorising one of its sets unlinks the solution entirely (it stays tutor-only, with a "link it again" warning) rather than leaving only open sets behind.
- The model leak check reads its verdict leniently (the model sometimes explains first), asks once more if there is none, and then fails closed: an unreadable answer counts as a leak. Helper calls get enough `max_tokens` for an explanation plus the JSON (200–600). An empty tutor reply is reported as an error, never saved.
- **Guidelines cannot change any of this.** They are inserted below the safety rules with an explicit note that they cannot unlock solutions, turn off citations or change modes, and the guard runs in code whatever the prompt says.
- **File serving:** `/files/{doc}` serves only documents that are public now. Staff links carry a staff scope and may open any material in their course, including solutions, for checking their library. Uploaded solutions are kept in the private bucket; the server simply never signs a student link for them until released.
- **Pause:** while a pause window is active, the chat endpoint returns 423 with the pause message and makes no model call.

### 9.1 AI-guided checkpoint assignments (`assignments.py`)
One instructor-written problem broken into sequential checkpoints (1 → 2 → … → Final Answer). Each checkpoint has a title, a question (`prompt`), a confidential `target_answer` and `rubric`, an optional `hint` and a point value; they are stored as JSON on the assignment, and `total_points` is their sum.
- **Authoring (staff).** `generate-checkpoints` drafts 3–4 checkpoints from the title, problem statement and solution notes (tutor model, one call, gated like a turn but not by pauses); points are rescaled to add up to 100 and nothing is saved. Staff edit the draft and `POST …/assignments` publishes it. Up to 8 checkpoints.
- **A turn** (`POST /api/assignments/{id}/turn`): the gates in `chats._check_turn_gates` (without the materials check, since the assignment carries its own problem) → **verifier** (helper model; sees the active checkpoint's target answer and rubric, returns `{passed, feedback}`, anything unreadable counts as not passed) → **Socratic tutor** (tutor model, buffered). The tutor's prompt holds the problem, the *established results* (answers of passed or skipped checkpoints) and the stage: nudge, hint (verifier skipped, the instructor's hint is given in the tutor's words), advance (congratulate, introduce the next checkpoint) or complete. It never contains solution notes, rubrics, or the target answer of the active or any later checkpoint.
- **Leak guard.** Before a reply is saved it is checked against every answer the student hasn't reached: `guard.short_answer_leaks` (the whole target, or any of its numbers the student hasn't been shown; shingles for long targets), then the model leak check (`tutor._llm_leak`, fails closed). A leaking reply is replaced with a fixed nudge (plus the instructor's hint), or, on an advance, a fixed "next checkpoint" message; the message is tagged `leak_blocked`.
- **State.** One `assignment_submissions` row per student, created on first open with an opening message (no model call). Passing awards the checkpoint's full points and opens the next one; the last one completes the submission. The state change and both messages are written in one transaction after `db.lock_row` on the submission, and refused (409) if the submission moved on meanwhile (two tabs). **Skip & reveal** marks the active checkpoint skipped (0 points), posts its target answer and opens the next one; no model call, but refused during a pause (423).
- **What students receive.** Only the problem, checkpoint titles and points, the prompt of open checkpoints and the result of passed or skipped ones. Target answers, rubrics, hints and solution notes never appear in a student response; locked checkpoints don't show their prompt (it may build on an earlier answer).
- **Staff.** The course listing adds started / completed / average score (staff previews excluded). `GET …/submissions` is the gradebook: per student, score, per-checkpoint status, attempts and the full transcript. Assignment conversations are graded work, so this is the one place staff read a student's conversation; the workspace tells students so (PRD §3.11). Tutor chats stay aggregate-only.

### 9.2 AI teaching assistant Q&A (`qna.py`)
A separate "Ask the course" section. The AI teaching assistant answers students' questions to the course staff from a reusable Q&A knowledge base, and sends anything it shouldn't or can't answer to a staff inbox shared by the owner and staff.
- **Knowledge base.** Staff upload past Q&A documents (PDF, Word `.docx`, `.txt`, `.md`). For `.docx`, the text is read from the zip's `document.xml`, and oversized XML is refused. A background job splits each document into ~6,000-character windows (at most 30), and one helper call per window extracts question-answer pairs with names and emails removed. Pairs start as `pending` and are never used until staff approve them (one by one, after editing, or all at once). Staff can also type pairs, or save one from an escalated thread with one click (`thread_id` records where it came from). Approved pairs marked `faq` are listed for every student, without the asker's name. A course holds up to 2,000 pairs. Removing a document drops its pending pairs and keeps the approved ones.
- **Rules** (`courses.qa_rules`, JSON). The assistant can be switched on or off. Each category (concepts, assignments, logistics, grades, extensions, personal, other) is set to answer or always escalate; grades, extensions and personal default to escalate. Free-text instructions (up to 4,000 characters) sit below the safety rules in the prompt, like guidelines.
- **A question** (`POST /api/courses/{id}/qna`) is saved first, so it can always reach staff. The steps, in order:
  1. Assistant off: escalate.
  2. A sensitive-topic regex (regrades, extensions, accommodations, illness…) matches a category set to escalate: escalate with **no model call**.
  3. The gates in `chats._check_turn_gates` (materials not required). If one fails, the thread stays `open` with the reason and an escalate button.
  4. The helper classifies the category. If that category escalates: escalate.
  5. Otherwise the tutor model answers, buffered. Sources are BM25 over approved pairs (top 4) plus the course's public chunks (top 3, hybrid). The problem set rule comes from `kb.turn_pset` (strictest wins).
- **Integrity.** The prompt never holds protected solution text, because retrieval is public-only. Every answer passes `kb.guard.leaks`. On a Graded set it also passes the model leak check against `solution_chunks_for`, which fails closed. A leak is replaced with a fixed reply and the message is tagged `leak_blocked`. `[S#]` citations are validated as in the tutor, and `[NC]` marks an answer the sources don't cover.
- **Escalation and replies.** The student can escalate at any time ("Not satisfied? Ask the course staff", with an optional note). Escalation makes no model call and passes no gate, so it works during a pause. Once a thread is escalated, follow-ups go to staff, not the assistant. Any staff member can reply, optionally resolving the thread, and the student sees the reply in the same thread with the staff member's name.
- **Privacy.** A thread is private to the student who asked. Staff see it only once it is escalated, whether by the student, a rule, or because the assistant was off. Until then the inbox shows counts only: questions, answered by the AI alone, escalated, waiting, per category (previews excluded). Q&A documents go to the model provider, so the upload asks staff to confirm they contain nothing they can't share.

## 10. Usage limits
- **Per-student allowance:** tokens (prompt + completion, all calls in the student's turns, including the background memory update) over a rolling window of the course's period (day, week or term; default week). Checked before each turn. The 429 message says when allowance frees up (the oldest usage in the window plus the period).
- **Course ceiling:** total tokens for the course, including staff preview chats and course-level helper calls (starter questions, mismatch checks). At the ceiling, students get "this course has used its plan's AI allowance".
- **App-wide safety limit:** `GLOBAL_DAILY_LIMIT` questions per rolling 24 hours across all courses (cost backstop; default 600). Assignment turns and Q&A messages count as questions.
- Assignment and Q&A calls (`assignment_*`, `qna_extract`, `qna_classify`, `qna_answer`, the leak check) carry `course_id` and `user_id` with `chat_id` empty, so they count toward the same allowance and ceiling.
- `usage_log` now records `course_id`, `user_id` and `chat_id` for every call; the background memory thread carries the same attribution.
- Embedding calls are logged with their cost but count 0 tokens toward allowances and the ceiling (§7.1).

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
| `courses` | `id`, `name`, `owner_id`, `status` (`pending`/`active`), plan (`student_seats`, `staff_seats`, `token_cap`, `cap_period`, `token_ceiling`, `price_cents`), access (`student_code`, `code_expires_at`, `email_domain`), `general_guideline`, `starter_questions`, `starter_version`, `content_version`, `index_version` (bumped when chunk embeddings are filled in), `setup` (checklist flags), `stripe_session_id`, `paid_at` |
| `memberships` | `course_id`, `user_id`, `role` (`owner`/`staff`/`student`), `status` (`active`/`removed`/`blocked`), unique per course and user |
| `staff_codes` | `course_id`, `code_hash`, `last4`, `expires_at`, `used_by`, `used_at`, `revoked_at` |
| `documents` | v0 fields + `course_id`, `status`, `status_detail`, `storage_path`, `content_type`, `pages`, `size_bytes`, `warning`, `rights_confirmed`, `mode`, `release_at`, `confirm_answers`, `uploaded_by`, timestamps |
| `solution_links` | `solution_id`, `pset_id` (one solution can cover several sets) |
| `chunks` | `id`, `doc_id`, `page`, `text`, `tutor_only` (1 for solution chunks), `embedding` (float32 unit vector; BLOB in SQLite, BYTEA in Postgres), `embed_model` |
| `guidelines` | tagged guidelines: `course_id`, `text`, `doc_ids` (JSON). The general guideline is on `courses`. |
| `pauses` | `course_id`, `starts_at`, `ends_at`, `message` |
| `chats` | `course_id`, `user_id`, `title`, `kind` (`chat`/`pset`/`review`/`quiz`), `doc_id` (attached material), `is_preview` |
| `messages` | v0 fields + on questions: `course_id`, `user_id`, `is_preview`, `doc_ids` (cited, JSON), `problem_doc_id`, `attempt_status`, `not_covered`, `leak_blocked` |
| `illustrations` | `id`, `chat_id`, `message_id`, `course_id`, `user_id`, `concept`, `skill`, `modality`, `title`, `rationale`, `spec_json`, `artifact_html`, `manim_code`, `created_at` |
| `assignments` | `course_id`, `title`, `problem_statement`, `solution_notes`, `total_points`, `checkpoints_json` (title, prompt, target_answer, rubric, hint, points), `published`, `created_by` |
| `assignment_submissions` | `assignment_id`, `course_id`, `user_id` (unique per assignment and user), `current_checkpoint`, `status` (`in_progress`/`completed`), `score`, `checkpoint_states_json` (status `active`/`locked`/`passed`/`skipped`, earned points, attempts), `is_preview` |
| `qa_sources` | `course_id`, `title`, `file_name`, `status` (`processing`/`ready`/`failed`/`no_text`), `status_detail`, `pairs_found`, `uploaded_by` |
| `qa_pairs` | `course_id`, `source_id`, `thread_id` (saved from an escalated thread), `question`, `answer`, `status` (`pending`/`approved`), `faq` |
| `qa_threads` | `course_id`, `user_id`, `title`, `category`, `status` (`open`/`ai_answered`/`escalated`/`staff_answered`/`resolved`), `escalated`, `is_preview`, `escalated_at`, `resolved_at` |
| `qa_messages` | `thread_id`, `role` (`student`/`ai`/`staff`/`system`), `author_id`, `content`, `citations`, `not_covered`, `leak_blocked` |
| `assignment_messages` | `submission_id`, `checkpoint_index`, `role`, `content`, `event_type` (`greeting`, `chat`, `hint_request`, `nudge`, `hint`, `advance`, `complete`, `skip`, `leak_blocked`) |
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
| `GET`, `POST /api/billing/test-checkout/{id}` | signed link, development only | Stands in for Stripe Checkout when no Stripe keys are set; 404 in production |
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
| `GET /api/chats/{id}`, `POST /api/chats/{id}/messages` | chat owner, active member | Read (problem set chats include the set's numbered problems from `knowledge.problems`); send (SSE: `delta`, optional `replace`, `done` with citations and the problem set rule, or `error`) |
| `GET /api/chats/{id}/illustrations`, `POST /api/chats/{id}/illustrate` | chat owner, active member | List or generate interactive concept illustrations (routes across `anatomy_isometric`, `manim_3b1b`, `explainer_diagram`, `explainer_storyboard`, gated by `_check_turn_gates` and leak guard) |
| `GET /api/illustrations/{id}/download?format=html|svg|py` | chat owner, active member | Download standalone interactive HTML, vector SVG, or ManimCE Python script |
| `GET /api/sources/{chunk}` | member of the chunk's course | A citation's passage, only if public now |
| `POST /api/courses/{id}/assignments/generate-checkpoints` | staff | Draft checkpoints with AI (not saved) |
| `GET`, `POST /api/courses/{id}/assignments` | member; create: staff | List (students: redacted, with their progress; staff: full, with stats); publish |
| `GET /api/assignments/{aid}` | member | The caller's workspace (created on first open), redacted (§9.1) |
| `POST /api/assignments/{aid}/turn`, `…/skip-checkpoint` | member | Verifier + Socratic tutor turn (`{content, hint}`); skip for 0 points |
| `GET /api/assignments/{aid}/submissions`, `DELETE /api/assignments/{aid}` | staff | Gradebook with transcripts; delete with all submissions |
| `GET`, `POST /api/courses/{id}/qna` | member | The caller's threads, the FAQ and which topics go to staff; ask a question |
| `GET /api/qna/{tid}`, `POST …/messages`, `…/escalate`, `…/resolve` | the asker (staff: escalated threads only) | Thread; follow-up; send to staff; resolve |
| `GET /api/courses/{id}/qna/inbox`, `POST /api/qna/{tid}/reply`, `…/save` | staff | Escalated threads and counts; reply; save the answer as a Q&A pair |
| `GET`, `PUT /api/courses/{id}/qna/rules` | staff | Assistant on/off, answer or escalate per category, instructions |
| `GET …/qna/knowledge`, `POST`/`DELETE …/qna/sources`, `POST`/`PATCH`/`DELETE …/qna/pairs`, `POST …/qna/pairs/approve` | staff | Q&A documents and pairs; review queue |

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
- **Automated** (129 pytest tests, mock LLM, mock checkout, local auth): the suite builds its own small **synthetic course** (a few text documents: notes, a problem set and its solution) in a temporary database, so it needs neither the 18.05 export nor any key, and it runs in GitHub Actions before every deploy. It covers sign-up and login, course creation and the checkout and webhook path (with locally computed Stripe signatures), Supabase JWT verification (with a locally generated ES256 key), codes, seat caps, removal and blocking, tenancy, uploads and statuses, modes and release, solution protection, guidelines in the prompt, pause, token caps, starter questions, the dashboard rules, checkpoint assignments (redaction, progression, skip, leak guard, gates, tenancy; `test_assignments.py`), the AI teaching assistant Q&A (extraction and review, rules, escalation, learning loop, gates, solution protection, privacy; `test_qna.py`) and the v0 migration. The same suite passes on SQLite and on Postgres (`TEST_DATABASE_URL`), and the v0 → v1 migration was rehearsed on a Postgres database built from v0's own schema code. GitHub Actions runs it on pull requests (`ci.yml`, which also builds the frontend) and before every deploy (`deploy-backend.yml`). An independent review of the backend (2026-10-20) reproduced 11 issues, from a laxer mode being selectable for a pasted Graded problem to a seat-cap race; all are fixed, each with a regression test in `tests/test_hardening.py`.
- **By hand** (2026-10-20, local server): the owner flow in a browser (sign up, create a course, test checkout, upload notes, a problem set and a linked solution, modes, guidelines, preview, members, dashboard, pause, plan), the student flow (join with a code, course home, review and problem set chats, phone layout), and six turns with the real model (AI_STRATEGY.md §7). **After the production deploy (2026-10-20):** the live backend reports Supabase Auth and Stripe; the production database migrated (v0 data kept as `v0_*`); the 18.05 demo course was created for the first real account, with sample dashboard data. **Not yet checked by hand:** a live Stripe test payment, password reset by email, and Google sign-in (not enabled).
- **Real-model leak evaluation:** `python -m app.evals --course-id <id> --pset "<title>"` (AI_STRATEGY.md §7). It costs real API calls, so it runs by hand, not in CI.

## 16. Configuration
New settings (see `.env.example` and `.env.production.example`):

| Variable | Where | Purpose |
|---|---|---|
| `AUTH_PROVIDER` | backend | `supabase` (production) or `local` |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | backend | Auth: JWKS and issuer; anon key handed to the browser |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | backend | Checkout and webhook (test-mode keys) |
| `APP_URL` | backend | Default return URL for checkout |
| `GLOBAL_DAILY_LIMIT` | backend | App-wide question limit (cost backstop) |
| `EMBED_MODEL` | backend | Embedding model for hybrid retrieval (default `openai/text-embedding-3-small`) |
| `EMBED_MIN_SIMILARITY` | backend | Cosine floor for embedding matches (default 0.35; recalibrate with `app.retrieval_eval` if the model changes) |

## 17. Production deployment
Same layout as v0: Vercel (frontend, builds from `main`), Fly.io (backend, GitHub Actions on `main`), Supabase (Postgres, Storage, now Auth). See the README for the v1 go-live checklist: Supabase Auth settings, Stripe keys and webhook endpoint, new Fly secrets, the demo course owner, and the first-start migration.

**CI:** the deploy workflow now runs the test suite before `flyctl deploy`, and `ci.yml` runs the tests and the frontend build on pull requests.

**First v1 deploy:** set the new Fly secrets first (`AUTH_PROVIDER`, `SUPABASE_ANON_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `APP_URL`); without them the app refuses to start. On first start the database is migrated (§12). The demo course is then claimed with `python -m app.ingest --owner-email …` run against the production database.

## 18. Decisions and open questions
| Decision | Choice | Alternative |
|---|---|---|
| Auth | Supabase Auth in the browser; backend verifies JWTs with JWKS | Proxy auth through our backend (shares one IP for Supabase rate limits) |
| Roles | Course memberships in our database | Roles in Supabase user metadata |
| Payment confirmation | Signed webhook, plus a server-side `retrieve` on return | Trust the success redirect |
| Price | One payment per term, formula in §5 **(build default)** | Subscription or flat tiers |
| Cap period | Rolling week **(build default)**, configurable per course | Per day or per term only |
| Per-course retrieval | Separate in-memory hybrid index (BM25 + embeddings, reciprocal rank fusion) per course, cache keyed by content version, open sets and index version | A shared index filtered per query; pgvector; embeddings alone (lose exact matches like "Problem 3"); a reranker |
| Embedding storage | Vectors as bytes on `chunks`, searched in memory with numpy | pgvector (would tie the code to Postgres; course-sized corpora don't need an ANN index) |
| Solution release | Public only when all linked sets are open | Any linked set open |
| Not-covered signal | `[NC]` marker from the tutor, phrase fallback | A separate classifier call per turn |
| Uploads processing | Background thread in the API process | A job queue and worker |

**Open questions**
- Retention (chats kept for the term plus 30 days) and read-only courses after the term are agreed in PRD §2.7 but not built yet.
- Background processing in the web process can be interrupted by a scale-to-zero stop; a real job queue is the upgrade if uploads grow.
- Retrieval still misses some paraphrases ("flip until heads" never reaches the geometric distribution). BM25 alone still returns weak matches for off-topic messages ("hi"); the tutor's `[NC]` rule handles those. A reranker is the next step if the retrieval eval shows a need.
- PyMuPDF flattens math; LaTeX-aware or page-image extraction is still open.
