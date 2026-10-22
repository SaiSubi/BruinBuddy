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
- **Concept Illustration Engine (`illustrate.py`):**
  - Routes concepts across `anatomy_isometric` (`wheresryan22/anatomy`), `manim_3b1b` (`adithya-s-k/manim_skill`), `explainer_diagram`, and `explainer_storyboard` (`iart-ai/explainer-video-skills`).
  - Uses only `public` chunks, passes explicit `attr` on `illustrate_route` and `illustrate_gen` calls, and runs `kb.guard.leaks` + `_llm_leak` on Graded problem sets, sanitizing to a conceptual walkthrough if any solution overlap is detected.
- **LLM Attribution & Cost Control (`llm.py`):**
  - Every `llm` call requires explicit `attr={"course_id": ..., "user_id": ..., "chat_id": ...}` (logged to `usage_log` for allowance enforcement). Never use `contextvars` because streaming turns cross thread boundaries.
  - Default to `BB_MOCK_LLM=1` for all dev and test runs. Real model turns cost ~$0.012 and `python -m app.evals` costs ~$0.15; always ask the user before running real LLM calls.
- **Checkpoint Assignments (`assignments.py`):**
  - `assignment_verify` (helper) is the only call that sees the active checkpoint's `target_answer`/`rubric`; `assignment_tutor` gets the problem, established (passed/skipped) results and the stage (`nudge`/`hint`/`advance`/`complete`), never solution notes or unreached answers. `assignment_gen` (tutor model) is the only call that sees solution notes.
  - Every tutor reply is checked with `guard.short_answer_leaks` (whole target, unseen numbers, shingles) and `tutor._llm_leak` (fail closed) against all unreached answers; leaks become `_safe_reply` and are tagged `leak_blocked`.
- **AI TA Q&A (`qna.py`):**
  - `qna_extract` (helper) turns documents into pending pairs; `qna_classify` (helper) routes by category; `qna_answer` (tutor model) answers from approved pairs + public chunks with `[S#]` citations and `[NC]`.
  - The problem set rule comes from `kb.turn_pset`. Every answer passes `kb.guard.leaks`, and Graded sets also `_llm_leak` on `solution_chunks_for`; leaks become `qna.SAFE_REPLY`. Staff instructions go below the safety rules (`TA_RULES`).
