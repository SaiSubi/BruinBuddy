# BruinBuddy — notes for Claude

An AI tutor sold per course: a professor pays (Stripe, test mode), uploads the course's materials and sets rules; students join free with a code. FastAPI backend (`backend/app`), React/Vite frontend (`frontend/src`), Postgres + Storage + Auth on Supabase, OpenRouter for the models. **Production is live** (Vercel + Fly.io).

Read before larger changes: [docs/PRD.md](docs/PRD.md) (what and why), [docs/TECHNICAL.md](docs/TECHNICAL.md) (architecture, data model, API, decisions), [docs/AI_STRATEGY.md](docs/AI_STRATEGY.md) (prompts, modes, evals), [docs/DESIGN.md](docs/DESIGN.md) (screens and flows).

## Never push to `main`
A push or merge to `main` **deploys production**: GitHub Actions runs the tests and `flyctl deploy` (backend), and Vercel rebuilds the frontend. GitHub can't enforce branch protection on this private repo, so this is on you:
- Work on a branch and open a pull request; never commit to, push to, or merge into `main` unless the user explicitly asks for that specific merge.
- Never run `fly deploy`, `fly secrets …`, `vercel --prod`, or scripts against the production database (`DATABASE_URL` from `.env.production`) without the user's explicit go-ahead.

## Commands
```bash
python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements-dev.txt   # setup
cd frontend && npm install && npm run build && cd ..                                              # frontend build (the backend serves it)
BB_MOCK_LLM=1 backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --port 8000      # run with a fake tutor (no key, no cost)
cd frontend && npm run dev                                   # frontend dev server on :5173, proxies /api to :8000
cd backend && ../backend/.venv/bin/python -m pytest -q       # 105 tests; temp SQLite DB, mock model, no keys needed
TEST_DATABASE_URL=postgresql://... ../backend/.venv/bin/python -m pytest -q   # same suite on a throw-away Postgres (UTF-8 DB)
../backend/.venv/bin/python -m app.ingest --owner-email you@example.edu       # 18.05 demo course (needs 18.05-spring-2022/)
../backend/.venv/bin/python -m app.seed                                        # sample dashboard data (labelled as sample)
../backend/.venv/bin/python -m app.evals --course-id 1 --pset "Problem Set 04" # leak prompts vs the REAL model (~$0.15): ask first
BB_MOCK_LLM=0 ../backend/.venv/bin/python -m app.retrieval_eval --course-id 1    # retrieval quality: BM25 vs embeddings vs hybrid (embeddings only, <$0.01)
```
Local mode needs no Supabase or Stripe: `AUTH_PROVIDER` empty means local email/password accounts, no `STRIPE_SECRET_KEY` means a built-in test checkout page. Both are refused in production.

## Map
| Path | What it does |
|---|---|
| `backend/app/main.py` | App, CORS, routers, `/api/config`, `/api/health` |
| `accounts.py`, `auth.py` | Who is calling: Supabase JWT (JWKS) or local accounts; session, file and signed tokens |
| `courses.py` | Membership dependencies (`get_member`/`get_staff`/`get_owner`), course view, settings, codes, join, guidelines, pauses, allowance math |
| `members.py` | Roster (remove, block), single-use staff codes |
| `billing.py` | Price formula, Stripe Checkout, webhook, confirm-on-return, dev test checkout |
| `materials.py`, `extract.py`, `storage.py` | Uploads, background processing, mismatch warnings, library, files in Supabase Storage or `data/uploads` |
| `knowledge.py`, `retrieval.py`, `embeddings.py`, `guard.py` | Per-course hybrid index (BM25 + embeddings) of what students may see, problem set modes, chunk embeddings and backfill, leak guard |
| `tutor.py`, `chats.py` | The tutor pipeline and the chat/SSE endpoints with their gates; `/files` and `/api/sources` |
| `dashboard.py` | Staff aggregates with the small-group rule |
| `llm.py`, `memory.py`, `starters.py`, `jobs.py` | OpenRouter client + mock, per-course memory, starter questions, background jobs |
| `db.py` | Schema, in-place migration from v0, SQL helpers |
| `ingest.py`, `seed.py`, `evals.py`, `retrieval_eval.py` | 18.05 demo course, sample data, real-model leak evaluation, retrieval evaluation |
| `backend/tests/` | Synthetic course fixtures in `conftest.py`; `test_hardening.py` holds the review regressions |
| `frontend/src/` | `App.jsx` (boot, routing), `auth.js`, `api.js` (all HTTP), `CourseHome`/`ChatView` (students), `staff/` (console tabs) |

## Rules that must not break
1. **Tenancy.** Every course-scoped route depends on `get_member`, `get_staff` or `get_owner`; chat routes also check the chat's `user_id`. A non-member gets 404, a removed or blocked member 403. Roles come only from `memberships`, never from the request.
2. **Students never get protected solution text.** What students may see is decided only in `knowledge.py` (`public`): solutions stay tutor-only until *all* their linked problem sets are open. The tutor model never receives protected solution text (only the checker does, via `solution_chunks_for`); Graded turns are buffered and pass the text guard and the model leak check before anything is sent; when several problem sets match a turn the strictest mode wins; removing a linked set unlinks its solutions. Don't loosen any of this. Student file links use the public scope; only staff listings mint staff-scoped links.
3. **No model call past a gate.** Pause windows, student allowances, the course AI budget and the app-wide limit are checked in `chats.post_message` before `run_turn`; keep new gates there.
4. **Payment.** A course becomes active only through `billing._activate`, after the signed webhook or a server-side Stripe lookup passes `_pays_for` (our metadata, paid, full amount in USD). The test checkout exists only without Stripe keys and outside production.
5. **Guidelines shape tone, not rules.** They sit below the safety rules in the prompt and must never be able to unlock solutions or change modes.
6. **Portable SQL.** Write `?` placeholders (translated for psycopg; a literal `%` is escaped for you), `ON CONFLICT`, `RETURNING`. No SQLite-only functions (e.g. `group_concat`). Run the suite on Postgres when you touch SQL. Seat counts and other count-then-insert logic take `db.lock_row` first.
7. **Usage attribution** is passed explicitly (`attr={course_id, user_id, chat_id}`) to every `llm` call; allowances depend on it. Don't switch to context variables: a streamed turn runs across threads.
8. **Production safety checks** in `config.check_production_settings` stay strict (Supabase auth, Stripe test keys, no mock model, strong `SECRET_KEY`).
9. **Secrets.** Never commit `.env*` (only the `.example` templates), never print keys in output, never put real keys in tests. The Supabase anon key is public by design.

## Conventions
- Add or update tests with every behaviour change (mock model; see `conftest.py` helpers). Fix a bug with a regression test.
- When behaviour, data model, API or prompts change, update the matching doc (TECHNICAL.md, AI_STRATEGY.md, DESIGN.md) in the same PR.
- Match the surrounding code: short module docstrings, comments only where the why isn't obvious, user-facing error messages in plain language.
- Frontend: all HTTP goes through `api.js`; routes are hash URLs (`router.js`); students must never load staff-only data.
- Stage files by path (`git add <files>`), not `git add -A` or whole folders: people keep personal, untracked notes in the checkout.
- `data/` (local DB, uploads, dev accounts) and `18.05-spring-2022/` are git-ignored and local to each machine; tests never touch them.
- Real-model calls cost money (about $0.012 per tutor turn): use `BB_MOCK_LLM=1` by default and ask before running evals or many real turns.
