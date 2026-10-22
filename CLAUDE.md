# BruinBuddy — notes for Claude

An AI tutor sold per course: a professor pays (Stripe, test mode), uploads the course's materials and sets rules; students join free with a code. FastAPI backend (`backend/app`), React/Vite frontend (`frontend/src`), Postgres + Storage + Auth on Supabase, OpenRouter for the models. **Production is live** (Vercel + Fly.io).

Read before larger changes:
- **Product & Architecture Docs:** [docs/PRD.md](docs/PRD.md) (what and why), [docs/TECHNICAL.md](docs/TECHNICAL.md) (architecture, data model, API, decisions), [docs/AI_STRATEGY.md](docs/AI_STRATEGY.md) (prompts, modes, evals), [docs/DESIGN.md](docs/DESIGN.md) (screens and flows).
- **Agentic Architecture & Collaboration:** [.claude/COLLABORATION.md](.claude/COLLABORATION.md) (mandatory end-to-end Git/GitHub workflow for the team), [.claude/README.md](.claude/README.md) (agents, memory, commands & rules overview), [.claude/memory/PROJECT_MEMORY.md](.claude/memory/PROJECT_MEMORY.md) (shared project memory).

## Git Collaboration, Branch Protection & Contributor Attribution

### 1. Human-Only Contributor Attribution (Mandatory)
- **The Git contributor must always be the human developer (e.g., `Nivesh`), NEVER Claude.**
- Before committing, verify `git config user.name` and `git config user.email` match the human developer (`Nivesh <kenivesh@gmail.com>`).
- **Never** include `Co-authored-by: Claude <noreply@anthropic.com>`, `Generated with Claude Code`, or any AI attribution footer in commit messages, pull request descriptions, or issues (enforced in [.claude/settings.json](.claude/settings.json)).

### 2. End-to-End Automated Git Flow (Issue → Branch → PR → Merge)
Many team members are not proficient with Git, so **the AI agent must execute the full Git/GitHub lifecycle automatically** following [.claude/COLLABORATION.md](.claude/COLLABORATION.md):
1. **Sync `main`:** `git checkout main && git pull origin main`
2. **Create a GitHub Issue (`#N`):** Run `gh issue create --title "<type>: <summary>" --body "..."` before writing code and capture `#<N>`.
3. **Create an Issue-Linked Branch:** `git checkout -b <type>/issue-<N>-<short-slug>` (`feat`, `fix`, `docs`, `chore`). **Never commit or push directly to `main`.**
4. **Implement, Verify & Update Docs:** Run backend tests (`pytest -q`), frontend build (`npm run build`), and update matching docs in `docs/` and `.claude/memory/`.
5. **Stage by Path & Commit as Human:** Stage specific files (`git add <file1> <file2>`, never `git add -A` or `git add .`) and commit with `<type>: <summary> (#<N>)` under the human developer's name only.
6. **Push & Open Linked PR:** Push branch and run `gh pr create` with `Closes #<N>` in the PR description so the issue is automatically linked and closed on merge.
7. **Verify CI & Merge:** A merge to `main` **deploys production** (GitHub Actions runs tests and `flyctl deploy`; Vercel rebuilds the frontend). Wait for CI checks (`gh pr checks <PR> --watch`) to pass, then squash-merge via `gh pr merge <PR> --squash --delete-branch` when approved/requested.
- Never run `fly deploy`, `fly secrets …`, `vercel --prod`, or scripts against the production database (`DATABASE_URL` from `.env.production`) without the user's explicit go-ahead.

## `.claude` Agentic System (Subagents, Memory, Commands, Rules & Skills)

Specialized agents in `.claude/agents/` each maintain persistent domain context in `.claude/memory/`:

| Agent | Agent Definition | Persistent Memory | When to Use |
|---|---|---|---|
| **Git Workflow Manager** | [.claude/agents/git-workflow-manager.md](.claude/agents/git-workflow-manager.md) | [.claude/memory/git-workflow-manager.md](.claude/memory/git-workflow-manager.md) | Creating issues, branching, committing (as human), opening PRs (`Closes #N`), checking CI, and merging |
| **Backend Architect** | [.claude/agents/backend-architect.md](.claude/agents/backend-architect.md) | [.claude/memory/backend-architect.md](.claude/memory/backend-architect.md) | FastAPI routes, Supabase Auth, Stripe billing, tenancy dependencies, materials, and portable SQL |
| **AI Tutor Specialist** | [.claude/agents/ai-tutor-specialist.md](.claude/agents/ai-tutor-specialist.md) | [.claude/memory/ai-tutor-specialist.md](.claude/memory/ai-tutor-specialist.md) | RAG retrieval, problem-set modes, solution leak guard (`guard.py`), `illustrate.py` animations, prompts, and OpenRouter LLM client |
| **Frontend Developer** | [.claude/agents/frontend-developer.md](.claude/agents/frontend-developer.md) | [.claude/memory/frontend-developer.md](.claude/memory/frontend-developer.md) | React/Vite SPA (`frontend/src`), student chat SSE, `IllustratePane.jsx`, citations, Staff Console tabs, and `api.js` |
| **QA & Security Auditor** | [.claude/agents/qa-security-auditor.md](.claude/agents/qa-security-auditor.md) | [.claude/memory/qa-security-auditor.md](.claude/memory/qa-security-auditor.md) | Writing/running `pytest` suites, `test_hardening.py` regressions, and pre-PR security/invariant audits |
| **Docs Maintainer** | [.claude/agents/docs-maintainer.md](.claude/agents/docs-maintainer.md) | [.claude/memory/docs-maintainer.md](.claude/memory/docs-maintainer.md) | Keeping `docs/*.md`, `README.md`, `CLAUDE.md`, and `.claude/memory/*.md` synchronized |

- **Slash Commands (`.claude/commands/`):**
  - [`/project:start-task`](.claude/commands/start-task.md) — Sync `main`, create a GitHub Issue `#N`, and check out `<type>/issue-N-<slug>`.
  - [`/project:verify`](.claude/commands/verify.md) — Run `pytest`, `npm run build`, and audit all 9 unbreakable rules + git attribution.
  - [`/project:ship`](.claude/commands/ship.md) — Verify, commit as human, push branch, open PR (`Closes #N`), watch CI, and squash-merge.
  - [`/project:sync-memory`](.claude/commands/sync-memory.md) — Sync `.claude/memory/` and `docs/` with recent code changes.
- **Visual Explainer Skills (`.claude/skills/`):** [anatomy](.claude/skills/anatomy/SKILL.md) (`wheresryan22/anatomy`) · [manim](.claude/skills/manim/SKILL.md) (`adithya-s-k/manim_skill`) · [explainer-video](.claude/skills/explainer-video/SKILL.md) (`iart-ai/explainer-video-skills`)
- **Modular Rules (`.claude/rules/`):** [git-and-attribution.md](.claude/rules/git-and-attribution.md) · [backend-and-sql.md](.claude/rules/backend-and-sql.md) · [tutor-and-leak-guard.md](.claude/rules/tutor-and-leak-guard.md) · [frontend-conventions.md](.claude/rules/frontend-conventions.md)

## Commands
```bash
python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements-dev.txt   # setup
cd frontend && npm install && npm run build && cd ..                                              # frontend build (the backend serves it)
BB_MOCK_LLM=1 backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --port 8000      # run with a fake tutor (no key, no cost)
cd frontend && npm run dev                                   # frontend dev server on :5173, proxies /api to :8000
cd backend && ../backend/.venv/bin/python -m pytest -q       # 143 tests; temp SQLite DB, mock model, no keys needed
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
| `tutor.py`, `chats.py`, `illustrate.py` | The tutor pipeline, concept illustration engine (Anatomy / Manim 3B1B / Explainer Video skills), chat/SSE/illustrate endpoints with their gates; `/files` and `/api/sources` |
| `assignments.py` | AI-guided checkpoint assignments: AI-drafted checkpoints, verifier + Socratic tutor turns, skip & reveal, redacted student views, staff gradebook |
| `qna.py` | AI teaching assistant Q&A: Q&A knowledge base (extraction, review, FAQ), rules, answering, escalation to the staff inbox |
| `dashboard.py` | Staff aggregates with the small-group rule |
| `llm.py`, `memory.py`, `starters.py`, `jobs.py` | OpenRouter client + mock, per-course memory, starter questions, background jobs |
| `tracing.py` | Optional Langfuse tracing: one trace per answer via `attr["trace_id"]`, confidential prompts withheld, off without keys |
| `db.py` | Schema (`illustrations`, `chats`, `messages`, etc.), in-place migration from v0, SQL helpers |
| `ingest.py`, `seed.py`, `evals.py`, `retrieval_eval.py` | 18.05 demo course, sample data, real-model leak evaluation, retrieval evaluation |
| `evals/` | What each eval measures, how to run it, latest results (`README.md`) and saved runs (`results/`) |
| `backend/tests/` | Synthetic course fixtures in `conftest.py`; `test_hardening.py` holds the review regressions; `test_illustrate.py` tests the Illustrate feature; `test_assignments.py` the checkpoint assignments; `test_qna.py` the Q&A assistant |
| `frontend/src/` | `App.jsx` (boot, routing), `auth.js`, `api.js` (all HTTP), `CourseHome`/`ChatView`/`IllustratePane`/`GuidedAssignments`/`QnA` (students), `staff/` (console tabs) |
| `.claude/` | Specialized agents (`agents/`), persistent memories (`memory/`), visual skills (`skills/`), slash commands (`commands/`), rules (`rules/`), and [COLLABORATION.md](.claude/COLLABORATION.md) |

## Rules that must not break
1. **Tenancy.** Every course-scoped route depends on `get_member`, `get_staff` or `get_owner`; chat routes also check the chat's `user_id`. A non-member gets 404, a removed or blocked member 403. Roles come only from `memberships`, never from the request.
2. **Students never get protected solution text.** What students may see is decided only in `knowledge.py` (`public`): solutions stay tutor-only until *all* their linked problem sets are open. The tutor model and illustration generator never receive protected solution text (only the checker does, via `solution_chunks_for`); Graded turns and illustrations pass the text guard and the model leak check before anything is sent; assignment checkpoints follow the same pattern (target answers and rubrics go only to the verifier, every tutor reply is leak-checked against unreached answers, student responses never carry them); Q&A answers retrieve public chunks only and pass the same guards; when several problem sets match a turn the strictest mode wins; removing a linked set unlinks its solutions. Don't loosen any of this. Student file links use the public scope; only staff listings mint staff-scoped links.
3. **No model call past a gate.** Pause windows, student allowances, the course AI budget and the app-wide limit are checked in `chats._check_turn_gates` (used by `post_message`, `post_illustrate`, `assignments.post_turn` and `qna._respond`) before running the tutor or illustration engine; keep new gates there.
4. **Payment.** A course becomes active only through `billing._activate`, after the signed webhook or a server-side Stripe lookup passes `_pays_for` (our metadata, paid, full amount in USD). The test checkout exists only without Stripe keys and outside production.
5. **Guidelines shape tone, not rules.** They sit below the safety rules in the prompt and must never be able to unlock solutions or change modes.
6. **Portable SQL.** Write `?` placeholders (translated for psycopg; a literal `%` is escaped for you), `ON CONFLICT`, `RETURNING`. No SQLite-only functions (e.g. `group_concat`). Run the suite on Postgres when you touch SQL. Seat counts and other count-then-insert logic take `db.lock_row` first.
7. **Usage attribution** is passed explicitly (`attr={course_id, user_id, chat_id}`) to every `llm` call; allowances depend on it. Don't switch to context variables: a streamed turn runs across threads.
8. **Production safety checks** in `config.check_production_settings` stay strict (Supabase auth, Stripe test keys, no mock model, strong `SECRET_KEY`).
9. **Secrets.** Never commit `.env*` (only the `.example` templates), never print keys in output, never put real keys in tests. The Supabase anon key is public by design.

## Conventions
- Add or update tests with every behaviour change (mock model; see `conftest.py` helpers). Fix a bug with a regression test.
- When behaviour, data model, API or prompts change, update the matching doc (TECHNICAL.md, AI_STRATEGY.md, DESIGN.md) and `.claude/memory/` in the same PR.
- Match the surrounding code: short module docstrings, comments only where the why isn't obvious, user-facing error messages in plain language.
- Frontend: all HTTP goes through `api.js`; routes are hash URLs (`router.js`); students must never load staff-only data.
- Stage files by path (`git add <files>`), not `git add -A` or whole folders: people keep personal, untracked notes in the checkout.
- `data/` (local DB, uploads, dev accounts) and `18.05-spring-2022/` are git-ignored and local to each machine; tests never touch them.
- Real-model calls cost money (about $0.012 per tutor turn): use `BB_MOCK_LLM=1` by default and ask before running evals or many real turns.
