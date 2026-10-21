# Memory — `ai-tutor-specialist`

*Last updated: 2026-10-20*

## 1. Tutor Pipeline & Academic Integrity Architecture
- **Pipeline (`tutor.py`):**
  1. **Retrieve (`retrieval.py`):** Per-course BM25 index over student-visible (`public`) chunks determined by `knowledge.py`.
  2. **Mode Resolution (`knowledge.py`):** Problem sets have three modes: `graded` > `practice` > `solutions_open`. If a turn matches multiple problem sets, the **strictest mode wins**.
  3. **Attempt Check (`tutor.py`):** Only the separate checker call receives protected solution chunks via `knowledge.solution_chunks_for`. The main tutor generator model **never** receives protected solution text.
  4. **Generate (`tutor.py`, `llm.py`):** System safety rules sit at the top of the prompt; professor teaching guidelines sit below and can only shape tone/pedagogy, never unlock solutions or override modes.
  5. **Leak Guard (`guard.py`):** For `graded` problem sets, responses are buffered (never raw-streamed unguarded) and must pass both the deterministic overlap guard (`guard.py`) and the model-based leak check before being sent to the student.
  6. **Citations:** Source links minted for students always use `public` scope.
- **Solution Unlinking Rule (`knowledge.py` / `materials.py`):**
  - A solution file remains tutor-only until *all* linked problem sets are in `solutions_open` mode.
  - Deleting or unlinking a problem set unlinks its associated solutions so they remain protected rather than defaulting to open.
- **LLM Attribution & Cost Control (`llm.py`):**
  - Every `llm` call requires explicit `attr={"course_id": ..., "user_id": ..., "chat_id": ...}` (logged to `usage_log` for allowance enforcement). Never use `contextvars` because streaming turns cross thread boundaries.
  - Default to `BB_MOCK_LLM=1` for all dev and test runs. Real model turns cost ~$0.012 and `python -m app.evals` costs ~$0.15; always ask the user before running real LLM calls.
