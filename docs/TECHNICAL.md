# BruinBuddy — Technical Architecture (v0)

> Status: v0 | Based on [PRD.md](PRD.md) and [DESIGN.md](DESIGN.md) | Last updated: 2026-10-19
> Scope: runs locally on one machine. Model choice and prompts are detailed in AI_STRATEGY.md.

## 1. System overview
```
Browser (React)
   │  HTTP + streaming (SSE)
   ▼
Backend (FastAPI, Python)
   ├─ Auth: name + role (+ access codes), signed bearer token
   ├─ Chat API ──► Tutor pipeline ──► OpenRouter (LLM API)
   │                  │  ▲
   │                  ▼  │
   │             Retriever ──► Index: public chunks (BM25, in memory)
   │                  │
   │             Checker ───► tutor-only solution chunks (SQLite)
   ├─ Memory worker ───────► OpenRouter (cheap model)
   └─ Dashboard API
SQLite (one file): users, chats, messages, memories, documents, chunks
Local files: 18.05 PDFs (served only if not tutor-only)
```
Everything runs on localhost. There is no cloud deployment in v0. The only outside calls go to OpenRouter.

## 2. Stack choices (v0)
| Area | Choice | Why |
|---|---|---|
| Backend | Python 3.12, FastAPI | Python is installed and has the PDF and ML libraries we need. |
| Frontend | React + Vite, KaTeX for math | Small SPA for the three screens in DESIGN.md. |
| Storage | SQLite locally; **Postgres on Supabase** in production (when `DATABASE_URL` is set) | The same SQL runs on both. Local dev needs no database server. |
| Retrieval | BM25 keyword search over about 1,100 chunks, built in memory at startup (no embeddings in v0) | No model download and no API cost. It handles course terms and symbols well. Embeddings or hybrid search are a later upgrade. |
| PDF extraction | PyMuPDF | `pdftotext` is not installed here. |
| LLM | **OpenRouter** (OpenAI-compatible API, called with the `openai` Python SDK). A stronger model for tutoring and the checker, a cheap model for query rewrite, memory, and the leak check. | One key and one API for any model. Model IDs live in `.env` (AI_STRATEGY.md). |
| Config and secrets | `.env` (git-ignored) holds `OPENROUTER_API_KEY` and model IDs | `.env.example` shows the variables. |

## 3. Course materials and ingestion

**Source:** `18.05-spring-2022/`. The PDFs are in `static_resources/`. Each document's metadata (title, type, license) is in `resources/<id>/data.json`.

**Which files are ingested** (`learning_resource_types` from `data.json`, plus filename checks):
| Material | Source tag | Treatment |
|---|---|---|
| Lecture notes (26) | `Lecture Notes` | Public, citable |
| Readings and class prep (36) | `Readings` (class prep files are tagged as readings, `class*-prep*`) | Public, citable |
| Problem sets (34: homework and in-class problems) | `Problem Sets` | Public, citable |
| Problem set solutions (34) | `Problem Set Solutions`, filename `*_sol*` | **Tutor-only** |
| Compiled "All … Reading" files, exams, exam solutions, studio and R files, and all others | — | Not ingested in v0 (the compiled readings duplicate the individual readings) |

The ingestion script logs what it skipped. Result: 1,102 public chunks and 252 tutor-only chunks.

**Pipeline** (`python -m ingest`, safe to re-run):
1. Read each `data.json` and select files per the table above.
2. Extract text per page with PyMuPDF. Keep the page number.
3. Split into chunks of about 300–500 tokens, never crossing a page boundary. Each chunk keeps `doc_id`, `page`, and `title`.
4. Store the chunks. Skip documents whose file hash is unchanged. (The BM25 index is built from the stored chunks when the server starts.)
5. Link each solution document to its problem set (for example `class07_pset_sol` ↔ `class07_pset`) by filename. Store the link on the document.
6. Print a report: counts per type, pages with little or no text, and unmatched solutions.

**Known weak spot:** math-heavy PDFs may extract badly (garbled formulas, broken tables). v0 accepts that and treats it as a risk to check by hand on a few documents. Page-image or LaTeX-aware extraction is a later option.

## 4. Tutor pipeline (one student message)
1. **Load context:** the chat's recent messages and the student's memory notes.
2. **Rewrite the query:** turn the latest message plus recent turns into a standalone search query. This can be skipped for the first message of a chat.
3. **Retrieve:** take the top-k (about 6) public chunks by BM25 score. Only chunks with `tutor_only = 0` are ever eligible. BM25 scores aren't calibrated, so v0 doesn't use a score cutoff beyond dropping near-empty matches. The tutor decides whether the retrieved text really answers the question.
4. **Detect an assigned problem:** if the message matches a problem set chunk above a similarity threshold, treat it as an assigned problem. See §5.
5. **Generate:** build a prompt from the system instructions (Socratic, cite sources, never reveal solutions, AI tutor role), memory notes, retrieved chunks labelled `[S1]…[Sk]`, and chat history. Stream the answer.
6. **Validate citations:** parse `[S#]` markers, drop any that don't map to a retrieved chunk, and convert the rest into citation objects (document, page, chunk text, file link).
7. **Guard output** (§5), then save the message, citations, and a record of the question.
8. **Update memory** in the background (§7).

If the materials don't cover the question, the tutor model says so (system prompt rule).

## 5. Keeping solutions from leaking
This is the highest-risk part of v0. The rule is enforced in code, with the prompt as a second layer.

- **Separate storage.** Solution chunks live in the same tables but have `tutor_only = 1`. The public retriever filters them out in the query itself, not in the prompt.
- **The tutor model never sees solution text.** When a student's message is about an assigned problem, a separate **checker** call receives the problem, the student's attempt, and the linked solution chunks. It returns only a structured result: `{attempt_status: correct | partially | incorrect | none, hint_level_feedback: "..."}`. The feedback is limited to a nudge such as "check the denominator in step 2". It must not state final values or the solution steps. The tutor model receives this result, not the solution.
- **Output guard.** Before a reply is sent, a check compares it against the linked solution chunks. It flags long text overlap and the presence of the solution's final answer. A flagged reply is replaced with a safe hint-only reply and the event is logged. A cheap LLM check can back up the text-overlap check.
- **No unlock path.** There is no setting, endpoint, or prompt phrase that turns the guard off.
- **File serving.** The backend serves only documents with `tutor_only = 0`, from an explicit allowlist in the database. Solution PDFs are never exposed by URL.
- **Citations** can only point to public chunks, since only those are ever retrieved for generation.

Tests for this section are in §10.

## 6. Data model (SQLite locally, Postgres in production)
| Table | Key fields |
|---|---|
| `users` | `id`, `name`, `role` (`student` \| `professor`), `created_at` |
| `chats` | `id`, `user_id`, `title`, `created_at`, `updated_at` |
| `messages` | `id`, `chat_id`, `role` (`user` \| `assistant`), `content`, `citations` (JSON), `memory_used` (JSON), `created_at` |
| `memories` | `id`, `user_id`, `text`, `topic`, `created_at`, `updated_at` |
| `documents` | `id`, `title`, `type`, `file_path`, `file_hash`, `tutor_only`, `linked_doc_id`, `license` |
| `chunks` | `id`, `doc_id`, `page`, `text`, `tutor_only` |
| `usage_log` | `ts`, `purpose`, `model`, `prompt_tokens`, `completion_tokens`, `cost` (for watching the budget) |

- A "question asked" is one `messages` row with `role = 'user'`. The dashboard count is `COUNT(*)` of those rows.
- Chats and messages are kept until deleted by hand. There is no retention policy in v0.

## 7. Memory
- **What it stores:** short notes per student, such as "reviewing conditional probability for exam 1" or "struggles with the denominator in Bayes' rule", and learning preferences. It stores nothing about the student beyond study context.
- **When it updates:** after each assistant reply, a background job sends the latest exchange and the current notes to a cheap model. The model returns a list of changes: add, update, or remove a note. The job applies them.
- **How it's used:** at the start of every turn, the student's notes (capped at about 15 most recent) are added to the prompt. The ids used are saved in `messages.memory_used` so the UI can show the "Used memory" line.
- **Limits in v0:** the student can't view, edit, or delete memory in the UI. To reset it, delete the rows by hand.

## 8. API
All routes except `/api/config`, `/api/session`, `/api/health`, and `/files/*` need `Authorization: Bearer <token>`. Role is checked on each route.

| Route | Who | Purpose |
|---|---|---|
| `GET /api/config` | any | Whether access codes are required (so the sign-in form can show the field). |
| `POST /api/session` | any | Sign in with `{name, role, code}`, creating the user if needed. Returns a signed token. |
| `DELETE /api/session` | any | Sign out. |
| `GET /api/chats` | student | List the student's chats. |
| `POST /api/chats` | student | Create a chat. |
| `GET /api/chats/{id}` | student (owner) | Get a chat and its messages. |
| `POST /api/chats/{id}/messages` | student (owner) | Send a message. Streams the reply via SSE: text deltas, then a final event with citations. |
| `GET /api/sources/{chunk_id}` | student | Get a citation's passage and document info. Public chunks only. |
| `GET /files/{doc_id}?t=…` | signed link | Serve a source PDF. The link is signed per document and expires after an hour. 404 if `tutor_only`. |
| `GET /api/dashboard` | professor | Return `{questions_asked: n}`. |

**Errors** use standard HTTP codes with `{error: "message"}`. If the LLM call fails, the user message is already saved and the client shows the retry state from DESIGN.md.

## 9. Security, privacy, cost
- **Auth:** sign-in is name plus role, gated by an access code when `STUDENT_CODE` / `PROFESSOR_CODE` are set. The server returns an HMAC-signed bearer token (7 days) and the browser sends it in a header, so the app works across domains with no cookies. This is demo-grade identity: anyone with the student code can use any student's name and read that student's chats. Real accounts (Supabase Auth) are the planned upgrade. In production, professor sign-in is disabled unless `PROFESSOR_CODE` is set, and the server refuses to start without a strong `SECRET_KEY`.
- **Authorization:** students can read only their own chats. Only professors can call the dashboard route. Solution documents are never served (§5).
- **Secrets:** the OpenRouter key lives in `.env`, which is git-ignored. It is never sent to the browser.
- **Data sent out:** student messages and retrieved course text go to OpenRouter and the model provider behind it. Memory notes go to the provider too. v0 has no real student data, but this must be revisited before real students use it.
- **Cost controls:** cap output tokens and top-k, skip re-ingesting unchanged files, use the cheap model for memory and the leak check, and log token usage per request so we can watch the $10–20 budget.
- **Licensing:** the About page credits MIT OCW 18.05 (CC BY-NC-SA 4.0). Non-commercial use only.

## 10. Testing
- **Ingestion:** counts match expectations per material type, every solution links to a problem set, no tutor-only chunk is marked public, and little-or-no-text pages are listed.
- **Citation integrity:** every citation in a reply maps to a chunk that was retrieved for that reply.
- **Leak tests:** a fixed set of prompts (asking for a pset answer directly, repeatedly, via roleplay, "ignore previous instructions", pasting the problem plus "the solution is…") run against the pipeline. The output must contain none of the solution's final answers or steps. This corresponds to PRD flow 3.
- **Access tests:** a student can't read another student's chat, can't call the dashboard, and can't fetch a solution PDF by id.
- **Flow checks:** run PRD flows 1–7 by hand. Automated evals are deferred (PRD §8).

## 11. Running it locally
```
backend/app/   FastAPI app, tutor pipeline, retrieval, guard, memory, ingestion
backend/tests/ pytest suite (runs on a copy of the DB with a mock LLM)
frontend/      React + Vite app (built into frontend/dist, served by the backend)
data/          bruinbuddy.db (git-ignored)
.env           OPENROUTER_API_KEY, model IDs (git-ignored; copy from .env.example)
```
See the README for the exact commands.

## 12. Decisions and open questions
| Decision | Choice | Alternative |
|---|---|---|
| Solution handling | Separate checker call so the tutor never sees solutions, plus an output guard | Give the tutor the solutions and rely on the prompt |
| Retrieval | BM25 in memory | Embeddings (local or hosted), or hybrid |
| LLM access | OpenRouter | Direct Anthropic API |
| Memory | List of short notes edited by a cheap model | A single rolling summary |
| Streaming | SSE | WebSockets |

**Open questions**
- Which LLMs do we use for tutoring, the checker, and memory? (→ AI_STRATEGY.md)
- Is PyMuPDF text good enough on the math-heavy notes? v0 extracts all pages with text, but formulas are flattened. Spot-check answers that depend on a formula.
- How do we reliably match a pasted problem to its problem set chunk when the student rewords it?
- Do we let the checker see only the final answer, or the whole worked solution?
- Is BM25 alone enough? Single-term questions ("what is variance") rank noisily, and v0 has no way to detect "not covered" from the score. Try embeddings or hybrid search next.

## 13. Production deployment
```
Browser ──► Vercel (static React build)
   │  VITE_API_BASE
   ▼
Fly.io (FastAPI container, scale-to-zero) ──► Supabase Postgres (transaction pooler)
   │                                       └─► OpenRouter
   └─ serves public PDFs from the image (solution PDFs are never in the image)
```
| Piece | Choice | Notes |
|---|---|---|
| Frontend | Vercel, built from `frontend/` | `VITE_API_BASE` is the Fly URL. Security headers in `frontend/vercel.json`. |
| Backend | Fly.io, `Dockerfile` + `fly.toml` | 512 MB shared CPU, auto-stops when idle (the first request after idle is slow). Health check at `/api/health`. |
| Database | Supabase Postgres | Connect with the **transaction pooler** URL. The schema is created on startup, with row-level security enabled and no policies, so Supabase's public REST API cannot read any table. The backend connects as a role that bypasses RLS. |
| Course data | Ingested once from the local course folder into Supabase (`DATABASE_URL=… python -m app.ingest`) | The 18.05 folder never leaves this machine. |
| PDFs | `deploy/make_pdfs.py` copies the 96 public PDFs (13.6 MB) into the image | Tutor-only solution text lives in the database only. |
| Secrets | `fly secrets` for the backend, kept locally in `.env.production` (git-ignored) | `SECRET_KEY`, `DATABASE_URL`, `OPENROUTER_API_KEY`, access codes, `ALLOWED_ORIGINS`. |

**Abuse and cost limits:** access codes gate sign-in, each student gets `DAILY_MESSAGE_LIMIT` questions per rolling 24 hours (default 40 in production), the whole app gets `GLOBAL_DAILY_LIMIT` (default 200, about $4 a day at $0.02 per turn), and CORS only allows `ALLOWED_ORIGINS`. Also set a credit limit on the OpenRouter key.

**Supabase features not used yet:** Auth, Storage, and realtime. They are candidates for the next pieces.

**Live (deployed 2026-10-19):** frontend https://bruinbuddy.vercel.app, backend https://bruinbuddy-api.fly.dev (region `sjc`; `sea` is deprecated), database on Supabase (us-west-2). The first Supabase load took about a minute from this machine.

**Redeploying**
- Backend: `backend/.venv/bin/python deploy/make_pdfs.py` (only if the PDF set changed), then `fly deploy --ha=false`. Change a secret with `fly secrets set KEY=value -a bruinbuddy-api` (this restarts the app).
- Frontend: `VITE_API_BASE` is stored in the Vercel project for Production. Vercel blocked a CLI deploy run from inside this git repo ("commit author doesn't have permission"), so deploy from a copy of `frontend/` that has no git history: copy it (with its `.vercel` folder) to a temp directory and run `vercel deploy --prod --yes` there. Connecting the Vercel project to the GitHub repo would remove the need for this.
- New course data: `DATABASE_URL=<supabase url> python -m app.ingest` (the URL must be percent-encoded if the password has special characters).
