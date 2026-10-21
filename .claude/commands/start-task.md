---
description: Start a new task by syncing main, creating a GitHub Issue (#N), and checking out an issue-linked branch (<type>/issue-N-<slug>).
---

Follow the workflow in `.claude/COLLABORATION.md` to start the task: `$ARGUMENTS`

1. **Verify Identity & Clean State:**
   - Run `git config user.name` and `git config user.email` to confirm the human contributor is set (e.g., `Nivesh`), never Claude.
   - Check `git status`. If on `main` with no uncommitted changes, run `git pull origin main`.
2. **Create GitHub Issue:**
   - Use `gh issue create --title "<type>: <summary>" --body "..."` with clear context and acceptance criteria based on `$ARGUMENTS`.
   - Record the returned Issue number `#<N>`.
3. **Create & Checkout Linked Branch:**
   - Run `git checkout -b <type>/issue-<N>-<short-slug>` (`feat`, `fix`, `docs`, or `chore`).
4. **Load Domain Context:**
   - Read `CLAUDE.md` and the relevant agent memory file in `.claude/memory/` before writing code.
