# BruinBuddy — AI Strategy

> Status: Draft placeholder | Owner: TBD | Last updated: 2026-10-16

## 1. AI product objective
Support understanding, retention, and independent problem-solving using authorized course context.

## 2. Tutoring behavior
- Prefer hints, explanations, and checks for understanding.
- State uncertainty and avoid inventing course policies or source references.
- Respect assignment rules and academic integrity.
<!-- TODO: Define tutoring modes and response guidelines. -->

## 3. Knowledge and grounding
<!-- TODO: Evaluate retrieval-augmented generation, chunking, metadata, document permissions, freshness, and citations. -->
Use only authorized course materials and enforce course/user access boundaries.

## 4. Model selection
<!-- TODO: Compare candidate models on teaching quality, accuracy, latency, privacy, and cost. -->
No model provider selected.

## 5. Agentic workflows
<!-- TODO: Determine if multistep planning, quizzes, revision loops, or tools add value over a simple RAG tutor. -->
Use bounded loops, explicit stop conditions, and limited tool permissions.

## 6. Evaluation framework
<!-- TODO: Create a representative question set and human review rubric. -->
Candidate dimensions:
- Grounded factual accuracy and citation quality
- Pedagogical usefulness and learning outcomes
- Hallucination and unsafe-answer rates
- Academic integrity and prompt-injection resistance
- Latency and cost per successful study session

## 7. Responsible AI and privacy
<!-- TODO: Specify data handling, opt-in, deletion, accessibility, and misuse mitigation. -->
Do not use student submissions or course content for model training without appropriate rights and consent.

## 8. Cost and scalability
<!-- TODO: Estimate tokens per session, retrieval spend, caching, quotas, and fallback behavior. -->

## 9. Experiments and roadmap
<!-- TODO: Prioritize baseline tutor, grounded tutor, quiz generation, and adaptive learning experiments. -->

## 10. Open decisions
<!-- TODO: Record chosen models, evaluation thresholds, and review owners. -->
