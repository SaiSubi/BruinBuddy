---
paths:
  - "backend/app/tutor.py"
  - "backend/app/knowledge.py"
  - "backend/app/retrieval.py"
  - "backend/app/guard.py"
  - "backend/app/chats.py"
  - "backend/app/llm.py"
  - "backend/app/evals.py"
---

# AI Tutor & Solution Leak Guard Rules

1. **Protected Solutions:** Student visibility is decided only in `knowledge.py` (`public`). Solutions stay tutor-only until *all* linked problem sets are `solutions_open`.
2. **Prompt Isolation:** The generator model in `tutor.py` never receives protected solution chunks; only the checker receives `solution_chunks_for`.
3. **Graded Turn Buffering:** When multiple problem sets match a turn, the strictest mode wins (`graded` > `practice` > `solutions_open`). Graded turns are buffered and must pass both `guard.py` text checks and the model leak check before sending.
4. **Guidelines vs. Safety:** Professor teaching guidelines sit below system safety rules and can never unlock solutions or override problem-set modes.
5. **Explicit Usage Attribution:** Pass `attr={course_id, user_id, chat_id}` explicitly to every `llm` call (never use `contextvars`). Default to `BB_MOCK_LLM=1` for tests and local runs.
