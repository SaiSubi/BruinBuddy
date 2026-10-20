# BruinBuddy

An AI-powered tutoring companion for UCLA students that complements Bruin Learn with personalized explanations, interactive Q&A, practice quizzes, and course-specific study support.

**v0** is a local class-project demo: a course-grounded tutor for MIT OCW 18.05 (stand-in course) with citations, multiple persistent chats, per-student memory, and a professor dashboard that counts questions. See [docs/PRD.md](docs/PRD.md), [docs/DESIGN.md](docs/DESIGN.md), [docs/TECHNICAL.md](docs/TECHNICAL.md), [docs/AI_STRATEGY.md](docs/AI_STRATEGY.md).

## Run it locally

Needs Python 3.12+ and Node 18+. The 18.05 course export must be in `18.05-spring-2022/` (git-ignored).

```bash
# 1. Configure (add your OpenRouter key to .env)
cp .env.example .env

# 2. Backend
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements-dev.txt
cd backend && ../backend/.venv/bin/python -m app.ingest && cd ..   # builds data/bruinbuddy.db (safe to re-run)

# 3. Frontend (built once; the backend serves it)
cd frontend && npm install && npm run build && cd ..

# 4. Start
backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --port 8000
```

Open http://127.0.0.1:8000, sign in as a student (any name) or professor.

- **No key yet?** Set `BB_MOCK_LLM=1` in `.env` to try the UI with a fake tutor (no cost, not real answers).
- **Frontend dev server:** `cd frontend && npm run dev` (port 5173, proxies to the backend on 8000).
- **Tests:** `cd backend && BB_MOCK_LLM=1 ../backend/.venv/bin/python -m pytest` (uses a temporary copy of the DB).
- Spend is logged per call in the `usage_log` table.

## Deploy

Production layout: Vercel (frontend) + Fly.io (backend) + Supabase (Postgres). Live: https://bruinbuddy.vercel.app (frontend) and https://bruinbuddy-api.fly.dev (backend). Students need the access code from `.env.production`. The backend redeploys automatically from GitHub Actions when backend files change on `main`. See [docs/TECHNICAL.md](docs/TECHNICAL.md) §13. Production settings live in `.env.production` (git-ignored; create it with `backend/.venv/bin/python deploy/init_env.py`, template in `.env.production.example`).

Course content: MIT OpenCourseWare 18.05, Spring 2022, CC BY-NC-SA 4.0. Non-commercial use only. Not affiliated with MIT or UCLA.
