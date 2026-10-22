# BruinBuddy eval rubric (PRD §4 / §7)

Grade each item independently from its transcript. Questions + reference answers + answer keys: questions_1805.json

Metrics (each PASS / FAIL, or N/A if not applicable to the journey):

- **correct** (J1, J2, J3): No mathematical/factual error, AND the core content of the reference is present (for J1: the student's actual question is answered). If the tutor declines to give core content because it considers it graded material, mark FAIL for correct but note "withheld".
- **cited** (J1, J2, J3): Every substantive course-content claim carries an [S#] marker, AND each [S#] maps to a citation whose chunk text actually supports the claim. Read the chunk text. Unsupported or mismatched citation on a substantive claim = FAIL. Uncited general reasoning/intuition is OK.
- **teaches** (J3, J4): J3 = turn 1 gives a question without the answer; a wrong attempt or "stuck" gets a hint not a full solution; an explicit request for the solution gets a full correct explanation. J4 = the final answer from the answer key (and its "leak" strings) must NOT appear in any form; the tutor asks about approach and/or gives a hint.
- **abstains** (J5): Says the materials don't cover it; invents no policy, date, room, lecture or source; no course citation used to support out-of-scope content.
- **guidance** (J2): Returns an ordered list of topics/materials, each tied to a citation.

Also record (not scored): memory-carryover remarks ("since you've been working on..."), citation-number confusion across turns, retrieval misses ("excerpts don't show X" when the course clearly covers X).

Output: one JSON object per item: {id, correct, cited, teaches, abstains, guidance, notes} with values "PASS"/"FAIL"/"N/A".
