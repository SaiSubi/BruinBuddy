# BruinBuddy — PRD (v0)

> Status: v0 | Scope: smallest thing we can build and run locally | Last updated: 2026-10-19
> Previous, larger draft kept in [PRD_draft_v1.md](PRD_draft_v1.md).

## 1. What we are building
BruinBuddy is an AI tutor for one course. A student chats with it, and it answers from the course materials, cites its sources, and guides the student toward the answer instead of handing over solutions. It remembers the student across chats. A professor can see how much it is being used.

- **v0 runs locally** on one machine. No hosting, no real login.
- **Demo course:** MIT OCW 18.05 (Intro to Probability and Statistics, Spring 2022), standing in for a UCLA course. The materials are CC BY-NC-SA 4.0, so credit MIT OCW and keep it non-commercial.
- It is a standalone web app with no Bruin Learn integration.

## 2. Problem
Students get stuck between lecture and problem sets. General chatbots either give the answer away or ignore how this course teaches and notates things. v0 gives them a course-grounded tutor that teaches and does not just answer. This is a working hypothesis. We have not interviewed users.

## 3. Users
| User | What they do in v0 |
|---|---|
| **Student** | Chats with the tutor, keeps several chats, returns later and is remembered. |
| **Professor** | Opens a dashboard that shows how many questions students have asked. |

## 4. v0 scope

### 4.1 Course materials (ingested ahead of time)
We ingest these four types from the 18.05 materials with a script. There is no upload UI.
- Lecture notes
- Readings
- Class prep
- Problem sets
- **Problem set solutions** are ingested but are **tutor-only**. See 4.3.

### 4.2 Tutor chat
- A student asks a question and the tutor answers from the ingested materials.
- Every substantive claim carries a **citation** that names the source document and location, for example "Class 7 notes, p. 3". The citation links to the source file.
- If the materials do not cover the question, the tutor says so and does not invent a source.
- The tutor can suggest what to review next when asked ("what should I study for conditional probability?"). This is a chat behaviour, not a separate feature.
- Tutor answers are labelled **AI-generated**.

### 4.3 Teaching behaviour and solutions
- The tutor teaches Socratically. It asks about the student's approach, gives hints, and explains concepts.
- The tutor **never reveals problem set solutions**. It does not quote them, state final answers to assigned problems, or reveal solution steps. It may use them privately to check whether a student's work is right.
- There is **no escape hatch** in v0. Asking again, or asking "just show me", does not unlock the solution.
- Because the tutor never reveals solutions, v0 has no professor toggle for this.

### 4.4 Multiple chats
- A student can start a new chat, switch between chats, and reopen old ones.
- Chat history is stored and persists across sessions on the local machine.

### 4.5 Memory
- The tutor keeps a persistent per-student **memory** that carries across chats. It holds things like topics the student is working on, where they struggled, and how they prefer to learn.
- The tutor uses the memory in new chats, for example "last time you were stuck on conditional probability."
- v0 assumption: memory is created automatically from chats and is not editable. Whether students can view or clear it is an open question (§8).

### 4.6 Identity
- Two roles, **student** and **professor**, with a simple local sign-in (pick or enter a name, no password, no UCLA SSO).
- Identity exists so history and memory belong to one student.

### 4.7 Professor dashboard
- v0 shows one number: the **total number of questions students have asked**.

## 5. Out of scope for v0
- Practice questions and quizzes
- Professor upload UI and tutor guidelines. Materials come from the ingestion script.
- Any way to unlock solutions
- Per-student or per-topic insights, and the unanswered-questions list
- Evaluation and metrics. We will define these later (§8).
- Hosting, real authentication, multiple courses, and privacy and compliance work
- Bruin Learn or any LMS integration
- Mobile optimization
- Grading, or anything that counts toward a real grade
- UCLA branding or marks

## 6. User flows (acceptance for v0)
1. **Concept question.** A student asks a concept question. The answer comes from the course materials, includes at least one citation, and does not contradict the notes.
2. **Study suggestion.** A student asks what to review for a topic. The tutor lists topics and materials, each cited.
3. **Assigned problem.** A student pastes a problem set problem and asks for the answer. The tutor does not give the answer. It asks about their approach and gives a hint, and it still refuses if they ask again.
4. **Not in the materials.** A student asks something the materials do not cover. The tutor says so.
5. **Multiple chats.** A student starts two chats, leaves, and comes back. Both chats are intact.
6. **Memory.** A student discusses a topic in chat 1. In a new chat 2 the tutor shows it remembers the earlier context.
7. **Dashboard.** After students ask questions, the professor sees the correct total count.

## 7. Constraints and risks
- **Solutions are in the corpus.** The tutor-only rule is the main risk. We need to test flow 3 hard.
- **Wrong or fake citations.** Citations must come from retrieved passages only.
- **PDF and math extraction.** Notes are math-heavy and extraction may garble formulas. Start with the four material types above, not everything.
- **Memory can be wrong or creepy.** It should record only study-relevant facts.
- **API budget** is roughly $10–20. Use a cost-efficient model and cache embeddings.
- **Content rights.** Credit MIT OCW, non-commercial only.

## 8. Open questions (not blocking v0)
- Can students see, edit, or clear their memory?
- How do we evaluate the tutor? Question set, metrics, and targets are deferred.
- Which model(s) fit the budget? (→ AI_STRATEGY.md)
- Do we later add practice questions, professor upload, guidelines, and richer insights?
- Does the "no escape hatch" rule stay once we have real users?
- Hosting, if we move beyond local.

## 9. Next
Use this PRD to write DESIGN.md: the student chat screen, chat list, professor dashboard, and the citation display. Then fill in TECHNICAL.md and AI_STRATEGY.md.
