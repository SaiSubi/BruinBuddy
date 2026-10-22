---
description: Verify tests/build, commit under the human developer's name (never Claude), push branch, create PR linked to Issue #N, check CI, and merge.
---

Follow `.claude/COLLABORATION.md` Steps 4–7 to ship the current work: `$ARGUMENTS`

1. **Ensure Issue & Branch Exist:**
   - Check `git branch --show-current`. If still on `main`, first create a GitHub Issue (`gh issue create`) to get `#<N>` and switch to a new branch `<type>/issue-<N>-<slug>`.
2. **Run Pre-Ship Verification:**
   - Run backend test suite: `cd backend && ../backend/.venv/bin/python -m pytest -q`
   - If frontend changed, run build: `cd frontend && npm run build`
   - Ensure matching docs in `docs/` and `.claude/memory/` are updated.
3. **Stage by Path & Commit (Human Contributor Only):**
   - Verify `git config user.name` is the human contributor (`Nivesh`), never Claude.
   - Stage only relevant files by explicit path (`git add <file1> <file2>`, never `git add -A` or `git add .`).
   - Commit with `<type>: <summary> (#<N>)` and **zero** `Co-authored-by: Claude` or AI footers.
4. **Push & Open Linked Pull Request:**
   - Push: `git push -u origin <branch>`
   - Open PR via `gh pr create --base main --head <branch> --title "<type>: <summary> (#<N>)" --body "Closes #<N>..."` (no AI signatures).
5. **Verify CI & Merge:**
   - Watch CI checks: `gh pr checks <PR_NUMBER> --watch`
   - Once CI passes, squash-merge and clean up branch: `gh pr merge <PR_NUMBER> --squash --delete-branch`
   - Sync local `main`: `git checkout main && git pull origin main`
