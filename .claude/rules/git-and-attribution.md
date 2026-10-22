# Git Collaboration & Contributor Attribution Rules

See full playbook: [.claude/COLLABORATION.md](../COLLABORATION.md)

1. **Human-Only Contributor Identity (Mandatory):**
   - The Git author and committer must always be the human developer (e.g., `Nivesh`), **NEVER** Claude.
   - **Never** append `Co-authored-by: Claude <noreply@anthropic.com>` or `Generated with Claude Code` to commits, pull requests, or issues.
2. **End-to-End Automated Git Flow for Every Task:**
   - **Step 1:** Sync `main` (`git checkout main && git pull origin main`).
   - **Step 2:** Create a GitHub Issue (`gh issue create`) and record `#<N>`.
   - **Step 3:** Checkout an issue-linked branch (`git checkout -b <type>/issue-<N>-<short-slug>`).
   - **Step 4:** Implement changes, run `pytest -q` and `npm run build`, and update matching docs.
   - **Step 5:** Stage files explicitly by path (`git add <file>`, never `git add -A` or `git add .`) and commit as the human developer referencing `(#<N>)`.
   - **Step 6:** Push the branch and open a PR (`gh pr create`) containing `Closes #<N>` in the body.
   - **Step 7:** Wait for CI checks (`gh pr checks`) and squash-merge (`gh pr merge --squash --delete-branch`).
