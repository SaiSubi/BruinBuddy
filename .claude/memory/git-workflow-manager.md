# Memory — `git-workflow-manager`

*Last updated: 2026-10-20*

## 1. Repository & Authentication Notes
- **Repository:** `https://github.com/SaiSubi/BruinBuddy.git` (Private repository).
- **Authentication:** On Windows, Git Credential Manager (`credential.helper=manager`) can hang in non-interactive shells when accessing this private repo. Always ensure `git config credential.helper "!gh auth git-credential"` is set so Git delegates authentication to the logged-in `gh` CLI without interactive prompts.
- **Contributor Identity:**
  - Configured local author: `user.name = Nivesh`, `user.email = kenivesh@gmail.com`.
  - **CRITICAL:** Never allow Claude or any AI tool to appear as author or co-author (`Co-authored-by: Claude` is strictly prohibited).

## 2. Branch, Issue & PR Conventions
- **Branch format:** `<type>/issue-<N>-<short-slug>` where `<type>` is one of `feat`, `fix`, `docs`, `chore`.
- **Commit message format:** `<type>: <concise summary> (#<N>)` (single-line or bulleted body, no AI trailers).
- **PR body requirement:** Must include `Closes #<N>` so merging the PR automatically closes the linked GitHub Issue.
- **Merge strategy:** `gh pr merge <PR_NUMBER> --squash --delete-branch` after verifying `gh pr checks <PR_NUMBER>` passes (`backend-tests` and `frontend-build`).
- **Untracked local paths to never stage:** `.env`, `.env.production`, `data/`, `18.05-spring-2022/`, `.claude/settings.local.json`. Always stage files by explicit path (`git add <path>`).
