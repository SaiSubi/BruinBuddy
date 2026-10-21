# BruinBuddy — Shared Project Memory

*Last updated: 2026-10-20*

## 1. System Snapshot
- **Product:** Per-course AI university tutor. Professors pay per course (Stripe Checkout, test mode), upload course materials, and configure problem set modes, teaching guidelines, exam pauses, and token allowances. Students join free with a course code.
- **Stack:**
  - **Backend:** Python 3.12+, FastAPI (`backend/app`), SQLite locally / Supabase Postgres in production (`db.py`), Supabase Storage / local `data/uploads/` (`storage.py`), OpenRouter (`llm.py`).
  - **Frontend:** React 18 + Vite (`frontend/src`), custom hash router (`router.js`), centralized HTTP client (`api.js`).
  - **Concept Illustration Engine (`illustrate.py`, `IllustratePane.jsx`):** Routes student concepts across three visual skill packs (`.claude/skills/anatomy`, `.claude/skills/manim`, `.claude/skills/explainer-video`) and renders interactive animations in-page with HTML, WebM video, PNG, SVG, and Manim `.py` downloads.
  - **Production:** Live on Vercel (`https://bruinbuddy.vercel.app`) + Fly.io (`https://bruinbuddy-api.fly.dev`). Merging to `main` automatically deploys production via GitHub Actions (`deploy-backend.yml`) and Vercel.

## 2. Team & Git Workflow Memory
- **Primary Contributor Identity:** Commits from this workspace must be authored by **Nivesh** (`user.name = Nivesh`, `user.email = kenivesh@gmail.com`).
- **Strict No-AI-Attribution Policy:** Never include `Co-authored-by: Claude` or `Generated with Claude Code` in commits, PRs, or issues. Enforced in `.claude/settings.json` and `.claude/COLLABORATION.md`.
- **Mandatory End-to-End Flow:** Every task follows `Issue (#N)` → `Branch (<type>/issue-N-<slug>)` → `Code + Tests + Docs` → `Commit (#N)` → `PR (Closes #N)` → `CI Pass` → `Squash Merge`.

## 3. Agent Registry & Memory Index
| Agent | Definition | Memory File |
|---|---|---|
| `git-workflow-manager` | [agents/git-workflow-manager.md](../agents/git-workflow-manager.md) | [memory/git-workflow-manager.md](git-workflow-manager.md) |
| `backend-architect` | [agents/backend-architect.md](../agents/backend-architect.md) | [memory/backend-architect.md](backend-architect.md) |
| `ai-tutor-specialist` | [agents/ai-tutor-specialist.md](../agents/ai-tutor-specialist.md) | [memory/ai-tutor-specialist.md](ai-tutor-specialist.md) |
| `frontend-developer` | [agents/frontend-developer.md](../agents/frontend-developer.md) | [memory/frontend-developer.md](frontend-developer.md) |
| `qa-security-auditor` | [agents/qa-security-auditor.md](../agents/qa-security-auditor.md) | [memory/qa-security-auditor.md](qa-security-auditor.md) |
| `docs-maintainer` | [agents/docs-maintainer.md](../agents/docs-maintainer.md) | [memory/docs-maintainer.md](docs-maintainer.md) |
- **UCLA Bruin Learn (Canvas LMS) UI & Accessibility Suite (`CanvasShell.jsx`, `accessibility.jsx`, `CourseHome.jsx`, `styles.css`):** Emulates UCLA Bruin Learn (Instructure Canvas LMS) with a global UCLA Blue left rail, slide-out white trays, course sub-navigation, UCLA Blue & Gold hero banner card, collapsible gray accordion sections, `📖 Immersive Reader` (TTS + Line Focus), and full Appearance & Accessibility controls (Light/Dark/High-Contrast themes, Protanopia/Deuteranopia/Tritanopia/Monochrome colorblind palettes, Dyslexia-friendly typography & paper tints, Font scaling, and Reduced Motion).
