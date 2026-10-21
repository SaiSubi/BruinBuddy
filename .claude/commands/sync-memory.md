---
description: Synchronize agent memory files (.claude/memory/) and project documentation (docs/) with recent code changes.
---

Inspect `git status` and `git diff main...HEAD` and update the relevant files:

1. **Agent Memory (`.claude/memory/`):**
   - Update `.claude/memory/PROJECT_MEMORY.md` and any domain memory (`backend-architect.md`, `ai-tutor-specialist.md`, `frontend-developer.md`, `qa-security-auditor.md`, `git-workflow-manager.md`, `docs-maintainer.md`) with newly added endpoints, schema tables, components, test fixtures, or operational notes.
2. **Project Docs (`docs/` & `CLAUDE.md`):**
   - Update `docs/TECHNICAL.md`, `docs/AI_STRATEGY.md`, `docs/DESIGN.md`, `docs/PRD.md`, or `CLAUDE.md` if architecture, prompts, or UI flows changed.
