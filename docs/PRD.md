# BruinBuddy — PRD (v1)

> Status: v1 built and live at https://bruinbuddy.vercel.app (2026-10-20). All sections are agreed. Sections 1, 5 and 6 and the decisions under the open questions were drafted by Claude from the build and agreed by the owner on 2026-10-20. | Last updated: 2026-10-20
> v0 (the deployed class demo) is in [PRD_v0.md](PRD_v0.md). Course requirements and rubric: Capstone "Build an AI Startup" (sign-up and login, AI backend, Stripe sandbox payments, live URL, write-up).

## Sections
1. Overview, problem, target users, and why AI
2. Accounts, access and payments
3. Professor features (course setup, materials, guidelines, modes, insights)
4. Student features (course home, tutor chat, memory)
5. Quality, errors and edge cases
6. Success metrics, risks, milestones

Open questions in §2.7, §3.10 and §4.12 now carry an **Agreed** line recording the decision; items marked "not built" are agreed but not implemented yet. TECHNICAL.md marks the same choices "(build default)".

Positioning against Bruin Learn and other LMSs is left open for the pitch. The product is the tutor, so v1 does not add LMS features such as rosters for grading, gradebooks or announcements.

---

## 1. Overview, problem, users and why AI

### 1.1 Product
BruinBuddy is an AI tutor sold to a course, not to a student. A professor (or the department) creates a course, pays for it, uploads the course's own materials and sets the rules. Students join free with a code and get a tutor that answers from those materials, cites the page it used, and coaches them through problem sets without handing over graded answers.

### 1.2 Problem
- **Students** get stuck between lecture and the problem set, usually at night or the day before a deadline, when office hours are over. General chatbots answer immediately but ignore how this course teaches and notates things, and they hand over full solutions, which doesn't help learning and puts students in an academic-integrity grey zone.
- **Professors and TAs** can't scale office hours, can't see where a class is stuck until exams are graded, and have no say in what a general chatbot tells their students. Many ban such tools rather than shape them.
- This is still a working hypothesis: we have not interviewed students or instructors (see §6.3).

### 1.3 Target users
| User | Who | What they need |
|---|---|---|
| **Buyer and course owner** | A professor running a large lower-division course (e.g. intro probability and statistics, 100–400 students), or a department paying for several courses | Better-supported students without losing control of integrity, a predictable cost, and a view of where students struggle |
| **Staff** | TAs and co-instructors | The same controls as the owner except billing, and less repetitive office-hours questions |
| **Student** | Undergraduates in that course | Help at any hour that matches the course, explains rather than tells, and is honest about what it doesn't know |

The demo course is MIT OCW 18.05 standing in for a UCLA course; the first real customer profile is a UCLA instructor of a large quantitative course.

### 1.4 Why AI, and why this design
- The help that unblocks a student is a conversation: understanding a half-formed question, reacting to a wrong attempt with the right next hint, re-explaining in the course's notation, and pointing to the exact page. Search can find a page but can't teach; a TA can teach but doesn't scale. An LLM grounded in the course materials does both.
- The risks of AI here (made-up facts, handing out solutions, ignoring the professor) are handled by design rather than by prompt alone: answers are grounded in and cited to the course's materials, solution text is never shown to the tutor for Graded sets, replies are checked in code before students see them, and the professor sets per-set modes and guidelines (§3).

### 1.5 Business model
The professor or department pays per course per term; students join free (§2). The price scales with seats and the per-student AI allowance, so revenue tracks model cost (§2.7, §6.2).

---

## 2. Accounts, access and payments

### 2.1 Model
A **professor or university pays per course. Students join free.** Each course is its own account with its own plan, materials, members and limits.

| Role | Who | Can do |
|---|---|---|
| **Course owner** | The professor or admin who creates and pays for the course | Set up the course, manage members and limits, see the roster |
| **Staff** | Additional professors or TAs, up to the plan's staff cap | Same as owner except billing, deleting the course, and adding staff |
| **Student** | Joins with the course code, up to the plan's seat cap | Use the tutor; see only their own chats |

One login can hold several roles: an owner of one course, a student in another. Roles come from **course membership stored in the database**, never from a field on the sign-in form.

### 2.2 Sign-up and login
- **Supabase Auth** with self-serve sign-up: email and password, plus Google sign-in. Password reset is included.
- The demo's name-and-access-code login is removed.
- A person who signs up through **"Create a course"** becomes an owner once payment succeeds. A person who signs up with a **course code** becomes a student of that course. Payment is the gate for owners; there is no manual approval.
- Email confirmation is on if a real email sender is configured, otherwise off for the demo (Supabase's default sender is rate-limited).

### 2.3 Creating and paying for a course
1. The owner signs up and chooses the plan: **number of staff accounts, number of student seats, and a per-student token cap**.
2. The price is calculated from those choices (formula to be decided, §2.7).
3. The owner pays with **Stripe Checkout in test mode** (sandbox card 4242 4242 4242 4242).
4. The course becomes **active only after the Stripe webhook confirms payment**. Until then it is in a pending state and students cannot join.
5. Production demo uses the Stripe sandbox only. No live payments in v1.

### 2.4 Joining a course (route B)
- Each course has **one common student code**, shared by the professor in class or on Bruin Learn.
- A student signs up or logs in, enters the code, and becomes a member. If the seat cap is reached, they see a clear "course is full" message.
- Course settings the owner controls:
  - **Rotate the code.** Existing students keep access; only the old code stops working.
  - **Email-domain restriction** (optional), for example `ucla.edu` only.
  - **Code expiry date** (optional).
- **Staff (extra professors or TAs) join with single-use staff codes.** The owner clicks "Add staff" to generate a code, which expires after 7 days, and gives it to one person. That person signs up with their own email and password, enters the code, and gets **staff access automatically**. The code is then used up. Codes count against the plan's staff cap, and the owner can revoke an unused code. The owner has full access from creation.
- The owner can **see who is staff and remove any staff member**. Staff cannot create staff codes, see billing, or delete the course.
- No approval queue in v1. An optional "require approval" toggle is a later addition (a pending state on the membership).

### 2.5 Roster and removal
- The owner and staff see a **roster**: name, email, joined date, token usage.
- They can **remove** a student (access ends immediately and the seat is freed) or **block** them (they cannot rejoin with the code).
- Removed students' chats are kept for the course but they can no longer sign in to it. Retention rules are an open question (§2.7).

### 2.6 Usage limits
- The owner sets a **per-student token cap** at setup and can change it later. It replaces the fixed 40-questions-a-day limit from v0. The cap covers a rolling period, with a default (period to be decided, §2.7).
- The plan also sets a **course-wide ceiling**, so a course cannot exceed what it paid for.
- A student at their cap sees a plain message and when it resets. Nothing is sent to the AI.
- Token usage is already logged per call, and will be attributed to the course and student.

### 2.7 Open questions
- **Pricing formula:** price per seat, per staff seat, per token cap, or a flat tier? Subscription per term, or one-time payment?
- **Cap period:** per day, per week, or per term?
- **Privacy:** can staff read an individual student's chats, or only aggregated insights? To be settled with the professor features (§3).
- **Retention:** how long are chats kept after a student is removed or a course ends?
- **What happens when payment lapses or the term ends:** read-only for students, or the course shuts off?

**Agreed (2026-10-20):**
- *Pricing (built):* one payment per course per 10-week term, no subscription: $19 base + $9 per staff account (owner free) + $2 per student seat for each 100k tokens of weekly allowance (minimum $0.50 per seat). Example: 40 students, 2 staff, 100k tokens a week = $117. The course's total AI budget is (students + staff + 1) × weekly allowance × 10 weeks. Details: TECHNICAL.md §5.
- *Cap period (built):* a rolling week by default; the owner can choose day, week or term at setup and change it later.
- *Privacy (built):* staff see aggregates only, never individual chats (as §3.6 says). Exception: AI-guided assignment conversations are graded work and visible to staff, and students are told so (§3.11). Q&A questions become visible to staff once the student, or a staff rule, sends them to staff (§3.12).
- *Retention (not built):* keep chats until the end of the term plus 30 days, then delete them; removed students' chats follow the same rule. Today nothing is deleted automatically.
- *Term end or lapse (not built):* after the term the course becomes read-only for students (history visible, no new questions) until renewed. Today a course stays active indefinitely.

### 2.8 Out of scope for v1
UCLA SSO, Bruin Learn or any LMS sign-in, unique per-student codes, bulk email invites, an approval queue, live-mode payments, refunds, proration, taxes and invoices.

### 2.9 Acceptance criteria
1. A new user can sign up, log in, and reset a password on the live site.
2. An owner can create a course, pay with the Stripe test card, and see it become active. A failed or cancelled payment leaves it pending.
3. A student can sign up, enter the course code, and use the tutor. A wrong, rotated or expired code is refused with a clear message.
4. The seat cap is enforced: the (cap + 1)th student is refused. Removing a student frees a seat; a blocked student cannot rejoin.
5. A student sees only their own chats, in their own courses. A user cannot reach another course's data or the owner screens by changing a request.
6. A student past their token cap gets the limit message and no AI call is made.

### 2.10 Effort (rough, on the existing codebase)
| Item | Effort | Depends on |
|---|---|---|
| Supabase Auth (sign-up, login, reset, token check in the backend) | M | none |
| Course and membership data model (courses, members, roles) | M | none; also needed for per-course materials in §3 |
| Student course code (seat cap, rotate, domain restriction, expiry) and single-use staff codes | S | membership model |
| Roster with remove and block | S | membership model |
| Stripe Checkout, webhook, pending-to-active | M | course model |
| Per-student and per-course token caps | S–M | usage logging (exists), membership model |
| Frontend: sign-up, create-course, join, roster screens | M | the above |

Rubric note: sign-up and login, and the Stripe checkout working in production, are listed must-haves in the course requirements.

---

## 3. Professor features

Staff means the owner and staff accounts (§2.1). Everything below applies to one course.

### 3.1 Setup flow
After payment (§2.3) a checklist guides the owner through: **upload materials → set problem set modes → write guidelines → try it as a student → share the student code.** Each step can be revisited at any time. The tutor is not open to students until the course is active and has at least one ready document.

### 3.2 Course materials
**Upload.** The professor picks a **category first**, then uploads one or more files under it.

| Category | Tutor treatment |
|---|---|
| Lecture notes, Readings, Other | Public and citable |
| Problem set | Citable. Has a mode (§3.4). |
| Solution | **Tutor-only**: never retrieved, cited or served to students, until its problem set is Released (§3.4) |

- **Solution linking.** Choosing "Solution" shows a dropdown of the course's existing problem sets. More than one can be selected, because one file can cover several sets. "Link later" is allowed: an unlinked solution is still tutor-only and protected, it just can't help the answer checker until linked.
- **Mismatch warning.** After upload a cheap model call checks each file and **warns only**, for example "this looks like a solution but is tagged as a reading." It never changes a category on its own. The human-picked category is the safety decision.
- **File types:** PDF and plain text or Markdown. PowerPoint and Word if time allows.
- **Limits:** a cap on files and pages per course, set by the plan.
- **Processing** runs as a background job. Each file shows **processing, ready or failed**. PDFs with no extractable text show "no text found" (scanned PDFs; no OCR in v1).
- **Rights.** The professor ticks a box confirming they have the right to use the materials.
- **Library.** Staff see every file with its category, status and linked problem sets, and can replace, re-categorise or delete it. Deleting a file removes it from the tutor's knowledge and from future citations.

### 3.3 Teaching guidelines
Guidelines are instructions to the tutor. They are **kept separate from course materials**: not citable, not searchable by students.
- **One general guideline** for the course: a text box (typed or pasted; a .txt or .md file can be uploaded), with starter prompts such as tone, tools and notation (for example "use R for simulations"), how to handle grading or admin questions, and what is in or out of scope.
- **Optional additional guidelines**, each **tagged to one or more materials**, such as "Lecture 3" or "Problem Set 4" ("Q3 expects an R simulation"). A tagged guideline applies when the tagged material is among the sources used for the answer, or is the detected problem set. If it conflicts with the general guideline, the tagged one wins for that material.
- Length caps apply to keep cost and prompt size bounded.
- **Guidelines cannot override safety rules.** They cannot turn off citations, reveal solutions, or change a problem set's mode. Only §3.4 does that.

### 3.4 Problem set modes and the exam pause
Each problem set has a mode, shown to students as a one-line rule in the chat (for example "Pset 4: hints only"). **Every student in the course gets the same rules.** There are no per-student exceptions in v1.

| Label | Tutor behaviour |
|---|---|
| **Graded: hints only** (default) | Hints and questions. No final answers or solution steps, however the request is phrased. Full solution protection and leak guard. |
| **Practice: full help** | Guided help. A worked explanation after an attempt or on request. |
| **After due date: solutions open** | Solutions become discussable and citable. Optional **release date** switches a set from Graded automatically. |

- New problem sets default to **Graded**, so a forgotten setting fails safe.
- Past exams are uploaded as Practice.
- A per-set yes/no setting, **"tell students if their final answer is correct"**, default **off**.
- **Pause tutor** is a course-wide, scheduled setting for exams. During the window students see a message that the tutor is paused, and no AI call is made. Exams are not a problem set mode, because detecting a pasted exam question is unreliable.

### 3.5 Try it as a student
Staff can open the student chat in their own course to test materials, guidelines and modes before sharing the code. Preview chats are labelled and **excluded from the dashboard**. Their token use still counts toward the course ceiling.

### 3.6 Dashboard
Staff see **aggregates, never individual students' chats.** Breakdowns are hidden when a group is very small (under 5 students). A time selector offers 7 days, 30 days and whole term.

| Panel | Shows |
|---|---|
| **Usage overview** | Active students, questions per day, seats used, tokens used against the course ceiling |
| **Most-asked materials** | Questions per cited document (lecture, reading, problem set), counted from the sources each answer used |
| **Unanswered questions** | Anonymised list of questions where the tutor could not find the answer in the materials. A list only; there are no actions attached in v1. |
| **Where students are stuck** | Per problem set: students asking, turns per student, and the answer checker's attempt results (correct, partial, incorrect) |
| **Student usage table** | Questions and tokens per student, to manage caps and abuse. Numbers only. |

**Demo data.** The demo course uses sample student questions so the dashboard has something to show. They are **labelled as sample data in the presentation**.

### 3.7 Out of scope for v1
Practice question generation, LMS sync, OCR, reading individual student chats, per-student exceptions, student feedback flags, model-clustered topic names, per-question stuck analysis, configurable hint intensity, actions on unanswered questions.

### 3.8 Acceptance criteria
1. A professor uploads files by category, links a solution to a problem set from the dropdown, sees processing status, and the new material is cited in tutor answers.
2. A solution file is never retrieved, cited or served while its problem set is Graded or Practice, and a mislabelled-looking file triggers a warning.
3. A failed or text-less PDF shows a clear status and does not break the course.
4. A guideline written by the professor visibly changes tutor behaviour. A tagged guideline applies to its material and not to others. A guideline that says "give the answer" does not unlock a Graded problem set.
5. In Graded mode the tutor refuses the answer under repeated and role-play pressure. Changing a set to After due date or Practice changes behaviour from the next message.
6. During a pause window, students get the pause message and no AI call is made.
7. Staff can preview as a student, and preview chats do not appear in the dashboard.
8. The dashboard shows the five panels, hides small groups, and never exposes individual chat content or student names in the unanswered list.

### 3.9 Effort (rough, on the existing codebase)
| Item | Effort | Depends on |
|---|---|---|
| Per-course data model and retrieval (materials, chunks, index per course) | M–L | §2 course model |
| Upload with category, solution dropdown, status, library | M | per-course model |
| Background ingestion job, caps, no-text handling | M | upload |
| Mismatch warning (one small model call) | S | upload |
| Guidelines: general plus tagged entries, prompt assembly | S–M | per-course model |
| Problem set modes, release date, confirm-answers setting, student-facing rule line | M | per-course model |
| Pause window | S | course model |
| Try as student (staff preview, excluded from stats) | S | per-course model |
| Dashboard (five panels, time selector, small-group rule) | M | message tagging below |
| Tag each question with cited documents, a not-covered flag, and course and student IDs | S | per-course model |
| Leak check that works without solution text (AI strategy) | S–M | modes |

### 3.10 Open questions
- File and page caps, and guideline length caps (set with the plan sizes in §2.7).
- If a problem set's mode changes mid-chat, does the new mode apply immediately? Proposed: yes, from the next message.
- How does the tutor know a question is "not covered" in a way that is reliable enough for the dashboard list?
- Solution PDFs have never been stored in the file bucket. Releasing a solution requires storing it privately and serving it only when Released.

**Agreed (2026-10-20; all built):**
- *Caps:* 300 files and 4,000 pages per course, 20 MB per file; the general guideline up to 4,000 characters; up to 20 material-specific guidelines of 1,000 characters each. Not yet tied to plan size.
- *Mode change mid-chat:* applies from the next message.
- *"Not covered" signal:* the tutor starts such replies with a hidden `[NC]` marker (a phrase check is the fallback); turns about a problem set never count as unanswered. Measure its accuracy on the evaluation set before relying on the dashboard list.
- *Solution files:* uploaded solutions are stored in the private bucket and served only to staff, or to students once every problem set they cover is open. Deleting or re-categorising one of a solution's sets unlinks it, so it stays tutor-only until relinked. The 18.05 demo solutions exist as text only.

### 3.11 AI-guided checkpoint assignments (issue #14)
A staff member writes one problem and its solution notes, clicks **Auto-generate checkpoints with AI** to draft 3–4 sequential checkpoints (each a question, a hidden target answer and rubric, a hint and points, adding up to 100), reviews and edits them, and publishes. Students open it in a **guided workspace**: the problem, a checkpoint stepper (Passed, Active, Skipped, Locked) and a Socratic chat.
- An answer checker decides whether the student's message reaches the active checkpoint. Reaching it earns **all of that checkpoint's points** and opens the next; the tutor congratulates, restates the result and asks the next question.
- Otherwise the tutor nudges with a question about the active checkpoint only. It is never given an answer the student hasn't reached, and its reply is checked in code and by the leak check before the student sees it.
- **Request hint** gives the instructor's hint in the tutor's words. **Skip & reveal** gives 0 points for the step, shows its result so the student isn't blocked, and opens the next step.
- Turns follow the same gates as the tutor (pause, allowance, course budget, daily limit); skipping is refused during a pause.
- **Privacy exception:** an assignment is graded work, so staff see each student's score, step-by-step progress and the assignment conversation in a gradebook. The workspace says so. Tutor chats stay aggregate-only (§3.6).
- Not in this version: editing a published assignment, due dates, drafts, exporting grades, LMS grade sync.

### 3.12 AI teaching assistant Q&A (issue #20)
Professors change TAs every term, but the content, the assignments and the questions students ask stay much the same. The course keeps its Q&A knowledge from term to term, so a new TA (and the AI) starts with it.
- **Knowledge base:** staff upload past Q&A documents (PDF, Word, text). The AI extracts question-answer pairs, which staff approve or edit before they are used. Staff can also add pairs by hand, and save any reply they give with one click, so the knowledge base grows every term.
- **Rules:** staff choose which kinds of questions the AI may answer and which always go to staff (by default grades, extensions and personal matters), and write instructions for it. Rules can't unlock solutions or change problem set modes.
- **Students** ask in "Ask the course". The AI answers right away from the knowledge base and materials, cites its sources, and says when it can't answer. "Not satisfied? Ask the course staff" sends the question to a shared inbox, where any professor or TA can reply.
- **Privacy:** a question is private to the student until it is escalated. After that, course staff can read that thread. Good answers can be published to a course FAQ without the asker's name.
- Not in this version: email notifications, assigning threads to a specific TA, Piazza/Ed and CSV importers, a public class board.

---

## 4. Student features

### 4.1 Approach
**Chat is the one place students get help.** A thin **course home** sits around it and launches chats with context attached. v1 adds no separate quiz, flashcard, planner or progress tools.

### 4.2 Joining
A student signs up or logs in, enters the course code (§2.4) and lands on that course's home. A wrong, expired or rotated code, a full course, and a removed or blocked student each get a clear message.

### 4.3 Courses
A student can be in several courses. A course switcher moves between them. **Chats and memory belong to one course.**

### 4.4 Course home
The home shows the course name, a banner if the tutor is paused (§3.4), the student's allowance meter (§2.6), and four entry points. Each ends in the same chat.

| Entry point | What it does |
|---|---|
| **Help with a problem set** | The student picks a problem set from the list, each shown with its mode ("hints only", "full help", "solutions open"). A chat opens with that set attached, so **the right mode applies and the checker finds the right solution even if the student rewords the question.** Pasting a problem in any chat still works, using v0's detection as a fallback. |
| **Review a topic** | Pick a lecture or reading. The chat starts with a request to review it, answered with ordered steps and cited materials. |
| **Quiz me** | Starts a chat with a practice request. The tutor asks one question at a time, grounded in the materials with citations. Questions are drawn from lecture notes, readings and Practice or open problem sets, **never from Graded problem sets.** |
| **Browse materials** | A read-only list of the course's documents by category. Opening one shows the source. Solutions are never listed unless their problem set is open. |

**Starter questions.** The home and every empty chat show three to four suggested questions, **generated from the course's materials** (one small model call per course after ingestion, regenerated when materials change). They are mostly concept and study-guidance questions drawn from lecture notes and readings, never the text of a Graded problem set. Clicking one sends it as the first message. Staff cannot edit them in v1.

If the course has no materials yet, the home shows a plain empty state. Students never see the staff setup screens.

### 4.5 Chat screen
Carried over from v0:
- A chat list in the sidebar, the conversation, and a source panel.
- Streaming answers, numbered citation chips that open the source passage, and a link to the original document.
- An **AI-generated** label on tutor messages, and math rendered with KaTeX.
- A "Used memory" line when memory shaped a reply.

New in v1:
- A one-line **rule for the current problem set** ("Pset 4: hints only").
- The pause message and the allowance limit message (§4.8).
- The About page states that the tutor can make mistakes, credits the course content where required, and says staff see aggregate usage and not individual chats.

### 4.6 Memory
Memory works as in v0: short study notes written automatically after replies, kept **per course**, used in later chats in that course. Students cannot view, edit or delete it in v1.

### 4.7 Responsive layout
Usable on a phone: the sidebar collapses into a menu and the source panel becomes a sheet. Not otherwise optimised.

### 4.8 Errors and limits
Every failure leaves the student's message in the thread with a clear next step.
- **AI failure or provider refusal:** a plain message with Retry.
- **Allowance reached:** a message with when it resets, and no AI call is made (§2.6).
- **Tutor paused:** the pause message, and no AI call is made (§3.4).
- **Removed or blocked:** access ends immediately, with a message that says to contact the instructor.
- **Session expired:** returns to login and keeps the draft where possible.
- **Not in the materials:** the tutor says so and offers what it can help with (v0 behaviour).

### 4.9 Out of scope for v1
A dedicated practice-question interface, flashcards, study planners, progress tracking, photo or image upload of problems, voice, notifications, sharing chats, thumbs up/down on answers, staff editing of starter questions, and student controls to view or delete memory, chats or data.

### 4.10 Acceptance criteria
1. A new student can sign up, enter a valid code and reach the course home. Bad codes give clear messages.
2. "Help with a problem set" opens a chat with that set attached, and the set's mode applies even when the student rewords the problem. The rule line is shown.
3. "Quiz me" asks cited questions from allowed materials and never from a Graded problem set.
4. "Browse materials" never lists or opens a solution while its set is Graded or Practice.
5. Chats and memory in one course are not visible in another. A student in two courses switches between them.
6. An answer from the materials has working citations and an AI-generated label. A question the materials don't cover gets the "not in the materials" reply.
7. A student at their allowance, in a paused course, or removed from the course gets the right message and no AI call is made.
8. The core flow works on a phone-sized screen.
9. Starter questions are specific to the course's own materials, cite real topics from them, and are not copied from a Graded problem set. Clicking one starts a normal cited chat.

### 4.11 Effort (rough, on the existing codebase)
| Item | Effort | Depends on |
|---|---|---|
| Course home with the four entry points and empty state | M | per-course model (§3.9) |
| Generated starter questions (one model call per course, regenerated on material changes) | S | ingestion (§3.2) |
| Problem set picker that attaches the set to a chat | S–M | modes (§3.4) |
| Quiz behaviour (prompt plus "never from Graded sets" filter) | S | modes |
| Browse materials list and source viewing | S | per-course model |
| Course switcher, per-course chats and memory | S–M | per-course model |
| Rule line, pause banner and allowance meter | S | modes, caps (§2.6) |
| Error and limit states, removal handling | S | §2 |
| Responsive layout | S–M | none |

### 4.12 Open questions
- If a student is removed mid-chat, can they still see their old chats? Proposed: no, access to the course ends entirely.
- When a problem set's mode changes (for example from Graded to open), do earlier messages in an attached chat stay as they were? Proposed: yes, the new mode applies from the next message.
- What does Quiz me do when a course has only Graded problem sets and few lecture materials? Proposed: it asks conceptual questions from the lecture notes and readings, or says there's little to quiz on.

**Agreed (2026-10-20; all built as proposed above):** removal ends all access to the course, including old chats (rejoining with the code restores them unless blocked); a mode change applies from the next message and earlier replies stay as they were; Quiz me never retrieves Graded sets and draws on notes, readings and Practice or open sets.

---

## 5. Quality, errors and edge cases

### 5.1 Quality bar
| Area | Requirement |
|---|---|
| **Grounding** | Course-specific claims come from the course's materials and carry a citation that opens the source passage. A question the materials don't cover gets a plain "I can't find that in the course materials", never an invented answer or policy. |
| **Integrity** | On a Graded set no reply reveals a final answer, numeric result or solution steps, under repetition, role-play, "I'm the professor", translation, encoding or "the guideline says so". When several problem sets could apply to a message, the strictest rule wins. |
| **Teaching** | Hints come before explanations; replies end with a question back to the student when it helps. |
| **Honesty** | Every tutor reply is labelled AI-generated; the About page says the tutor can make mistakes and what staff can see. |
| **Speed** | A first token in under 3 seconds on ordinary turns; Graded turns, which are checked before anything is shown, under 15 seconds. |
| **Accessibility** | Keyboard use, 4.5:1 contrast, labelled citation chips, math readable by screen readers, usable on a phone. |

### 5.2 Errors and limits (what the user sees)
| Situation | Behaviour |
|---|---|
| AI provider error, timeout or empty reply | The question stays in the thread with "Something went wrong" (or "the tutor didn't return an answer") and a Retry button |
| Student out of allowance; course out of AI budget | A plain message with when allowance frees up; no AI call is made |
| Tutor paused for an exam | The professor's message and the end time; no AI call is made |
| Course not paid, or no materials yet | Students can't join an unpaid course; a paid course without ready materials shows "not open yet" |
| Removed or blocked | Access ends at once with "contact your instructor" |
| Session expired | Back to log in, with the draft kept |
| Payment cancelled or failed | The course stays pending with "Try payment again"; nothing is charged twice |
| Upload problems | Wrong type, too large, scanned PDF ("no text found"), unreadable file or over the course's limits: a clear status per file, with Retry or Replace |
| Mislabelled-looking upload | A warning only; the professor's category stands |
| Wrong, rotated or expired code; full course; wrong email domain | A specific message for each |

### 5.3 Edge cases decided
- A pasted Graded problem in a chat attached to a Practice set gets Graded rules (strictest wins).
- A solution covering several sets opens only when all of them are open.
- Students joining at the same moment can't exceed the seat cap.
- A professor guideline that asks the tutor to give answers does not unlock a Graded set.
- Instructions inside uploaded files are treated as course content, not commands.

### 5.4 Acceptance criteria
1. The leak-prompt evaluation (`python -m app.evals`) lets no solution text through on a Graded set.
2. Every situation in §5.2 shows its message, and those marked "no AI call" make none (covered by the automated tests).
3. The automated test suite passes before every deploy.

---

## 6. Success metrics, risks and milestones

### 6.1 Quality metrics (measured on a fixed evaluation set)
| Metric | Target |
|---|---|
| Answers correct against the course materials | ≥ 90% on a 25-question set |
| Citations that point to a passage supporting the claim | ≥ 90% |
| Socratic behaviour on assigned problems (hints, not answers) | ≥ 90% |
| Solution leaks on the leak-prompt set | 0 |
| "Not covered" flag agrees with a human judgement | ≥ 80% (it feeds the dashboard) |

Today: the leak set passes (0 leaks in two runs); the 25-question correctness set is not built yet (AI_STRATEGY.md §7).

### 6.2 Product and business metrics (once real courses run)
| Metric | Why it matters | Target for a pilot term |
|---|---|---|
| Courses created → paid | Owner onboarding works | ≥ 70% |
| Paid courses with materials uploaded and the code shared within a week | The setup checklist works | ≥ 80% |
| Share of enrolled students active each week | Students find it useful | ≥ 40% |
| Questions per active student per week | Habit, and cost planning | 5–20 |
| Unanswered rate | Material gaps the professor can fix | < 10% of questions |
| Model cost as a share of the course's price | Margin | < 40% |
| Professor would renew next term | The buyer's verdict | Yes, from at least 2 of 3 pilot instructors |

### 6.3 Risks
| Risk | Mitigation |
|---|---|
| Solution leakage on a Graded set | Tutor never sees protected solution text; buffered, code-checked replies; strictest-mode rule; leak evaluation before prompt changes |
| Wrong or unsupported answers | Retrieval from the course's materials only, citations, "not covered" replies, the correctness evaluation (to build) |
| Problem demand is unproven | Interview students and instructors before a pilot; the sample-data dashboard is for demos only |
| Cost outruns price | Per-student allowances, a course AI budget, an app-wide daily limit, per-call cost logging |
| Student privacy | Aggregates only for staff, small groups hidden; a data and retention review before real students (FERPA) |
| Content rights | Professors confirm rights on upload; the demo credits MIT OCW (CC BY-NC-SA, non-commercial) |
| Email limits break sign-up or password reset at scale | Supabase's built-in mailer is for the demo; add custom SMTP before a pilot |
| One maintainer can deploy production | Tests run before every deploy; add required reviews on `main` |
| Weak retrieval on short or symbol-heavy questions | Hybrid or embedding retrieval is the next upgrade |

### 6.4 Milestones
| When | Milestone | Status |
|---|---|---|
| 2026-10-19 | v0 class demo live | Done |
| 2026-10-20 | v1 live: accounts, Stripe test-mode payments, uploads, modes, guidelines, dashboard | Done |
| Next | End-to-end check on the live site: test payment, student join, password reset | To do |
| Before the final presentation | Correctness evaluation set; capstone write-up (4–5 pages); rehearsed demo | To do |
| After the class | Instructor interviews and a one-course pilot; retention and term-end rules; custom email; Google sign-in | Proposed |

