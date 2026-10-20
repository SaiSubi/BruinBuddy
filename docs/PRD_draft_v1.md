# BruinBuddy — Product Requirements Document (PRD)

> Status: Draft v1 (class-project demo) | Owner: TBD | Last updated: 2026-10-19

## 1. Product overview
BruinBuddy is an AI study companion for a single course, built as a class-project demo. Students get Socratic study guidance, practice questions, and explanations grounded in the course materials, with visible citations. A professor uploads materials, sets tutoring guidelines, and sees how students are doing.

BruinBuddy is a standalone web app. 

**Demo course:** an intro probability and statistics course, using the public MIT OCW 18.05 (Spring 2022) materials as a stand-in for UCLA course content. They are licensed CC BY-NC-SA 4.0, so the demo must credit MIT OCW and stay non-commercial.

## 2. Problem statement
Students in a probability and statistics course get stuck between lecture and problem sets. Office hours are limited, and general-purpose chatbots either hand over final answers (bad for learning and academic integrity) or ignore what this course actually teaches and how it notates things. Professors have no view into where students are struggling.


## 3. Target users and use cases
| User | Needs |
|---|---|
| **Student** (intro prob/stats) | Understand a topic, find what to study next, practice with feedback, ask course-specific questions and trust the answer is sourced. |
| **Professor / instructor** | Upload course materials, control tutor behavior, see aggregate and per-student signals on struggle areas. |

Priority study situations: reviewing a class topic, preparing for a problem set (without getting the answers), and exam prep with practice questions.

## 4. Goals and success metrics
This is a demo, so the goal is to show cited, correct teaching. Metrics are measured on a hand-built question set (about 25 questions, written from the course materials).

| Goal | Metric | Demo target |
|---|---|---|
| Correct | Answer is correct against the reference solution or notes | ≥ 90% |
| Cited | Every substantive claim carries a citation that points to a real source passage and supports the claim | ≥ 90% |
| Teaches | Tutor in Socratic mode guides with hints or questions rather than giving the final answer to assignment-style problems | ≥ 90% |
| Works end to end | Student and professor flows complete live in the Thursday demo with no manual intervention | Yes / no |

Out of scope for now: engagement metrics, learning-outcome studies, satisfaction surveys.

## 5. MVP scope (v1: build today)

**Student**
1. **Course-grounded tutor chat** with citations to specific materials, e.g. "Class 7 notes, p. 3". Citations link to the source document.
2. **Study guidance.** Given a topic or an upcoming exam or pset, suggests what to review, in what order, and which materials to read.
3. **Practice questions and explanations.** The tutor generates or retrieves questions on a topic. It checks the student's attempt Socratically (hints first, then progressively more explanation), and shows a full explanation only once the student asks for it or has attempted the problem.
4. Visible **"AI-generated"** labelling, distinct from official course material.

**Professor**
5. **Upload materials** (PDF / text) into the course library.
6. **Tutor guidelines:** a free-text instruction box (e.g. "never give final numeric answers on pset problems", "use R for simulations") that is added to the tutor's instructions.
7. **Basic student insights:** number of sessions, most-asked topics, practice question results (attempted / correct), and a list of questions the tutor could not answer from the materials.

**Roles and access:** two roles (student, professor) with simple demo login. No UCLA SSO.

**Content handling:** solution documents (pset and exam solutions) are indexed as **tutor-only**. The tutor may use them to check the student's work, but must not quote or reveal them directly while the item is flagged as an active assignment. The professor can toggle this.

## 6. Out of scope
- Bruin Learn or any LMS integration
- Real authentication, multi-course, multi-tenant support, and production-grade privacy controls
- Mobile app (the web app should be usable on a phone, but is not optimized for it)
- Adaptive learning or long-term student modeling
- Grading, or anything that counts toward a real grade
- Agentic multistep workflows beyond a simple retrieve-then-answer loop
- Using UCLA marks or branding
- Any behaviour that completes graded work for students (see §5 on solutions handling)

## 7. User journeys and acceptance criteria

**J1. Student asks a concept question**
*Given* a student asks "why does Bayes' theorem need the prior?", *then* the answer is grounded in course materials, includes at least one citation, and does not contradict the notes.

**J2. Student asks for study guidance**
*Given* "I have an exam on conditional probability; what should I do?", *then* the tutor returns an ordered list of topics and specific materials to read, each with a citation.

**J3. Student practises**
*Given* the student requests practice on a topic, *then* the tutor presents a question, waits for an attempt, gives a hint when the attempt is wrong or the student is stuck, and gives a full explanation only after an attempt or an explicit request.

**J4. Student asks for a pset answer**
*Given* the student pastes an assigned problem and asks for the answer, *then* the tutor does not give the final answer. It asks about their approach and gives a hint.

**J5. Out-of-scope or unknown question**
*Given* a question the materials do not cover, *then* the tutor says so rather than inventing a source or course policy.

**J6. Professor uploads and configures**
*Given* a professor uploads a PDF and saves guidelines, *then* the new material is retrievable and cited in tutor answers, and the guidelines visibly change behaviour in the next session.

**J7. Professor reviews insights**
*Given* students have used the tutor, *then* the professor dashboard shows the metrics in §5 item 7.

## 8. Risks and dependencies
- **Hallucinated or wrong citations.** Mitigation: citations come from retrieved passages only, and they are checked against the question set.
- **Solution leakage.** Solutions are in the corpus. Mitigation: tutor-only flag plus an eval for J4.
- **Math rendering and PDF extraction quality.** Notes are math-heavy; extraction may mangle formulas and tables. Mitigation: start with the lecture notes and a handful of key documents rather than all 183 PDFs.
- **API budget of $10–20.** Mitigation: choose a cost-efficient model, cap tokens per request, cache embeddings, and don't re-ingest unnecessarily.
- **One-day build timeline.** Mitigation: keep the dashboard minimal and cut features before the core tutor loop.
- **Content rights.** OCW is CC BY-NC-SA 4.0: attribute, non-commercial only, and share-alike for derivatives.

## 9. Open questions
- Which model(s) fit the $10–20 budget while giving good teaching quality? (→ AI_STRATEGY / TECHNICAL)
- Which subset of the materials do we ingest for v1? (Proposal: lecture notes, readings, class prep, and problem sets; solutions flagged tutor-only.)
- Where does it run for the demo: local machine or hosted?
- Who writes the evaluation question set, and who reviews it?
- v2 direction, to be decided after the demo.

## 10. Milestones
| When | Milestone |
|---|---|
| Mon 10/19 (today) | PRD agreed; ingestion and citation-grounded tutor chat working end to end |
| Tue 10/20 | Practice questions, Socratic mode, professor upload and guidelines, basic insights |
| Wed 10/21 | Evaluation run on the question set, bug fixes, demo script and rehearsal |
| Thu 10/22 | Demo / deadline |

*Dates are based on "deadline Thursday"; adjust if the actual deadline differs.*
