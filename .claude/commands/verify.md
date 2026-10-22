---
description: Run the complete BruinBuddy verification suite (pytest, frontend build, security/tenancy/leak-guard audit, and git attribution check).
---

Run a full verification check using the `qa-security-auditor` checklist:

1. **Backend Test Suite:**
   - Run `cd backend && ../backend/.venv/bin/python -m pytest -q` (with `BB_MOCK_LLM=1`).
2. **Frontend Production Build:**
   - Run `cd frontend && npm run build`.
3. **Invariant Audit (`git diff`):**
   - Confirm tenancy dependencies (`get_member`/`get_staff`/`get_owner`), solution protection (`knowledge.py`, `guard.py`), pre-turn gates (`chats.post_message`), Stripe `_pays_for` / `_activate`, portable `?` SQL, and explicit `llm` usage attribution remain intact.
4. **Git & Secrets Check:**
   - Run `git status` and confirm no `.env*`, `data/`, or keys are staged, and `git config user.name` is set to the human contributor (`Nivesh`).
