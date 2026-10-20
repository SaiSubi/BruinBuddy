# BruinBuddy — PRD (v1, in progress)

> Status: draft, being written section by section | Last updated: 2026-10-20
> v0 (the deployed class demo) is in [PRD_v0.md](PRD_v0.md). Course requirements and rubric: Capstone "Build an AI Startup" (sign-up and login, AI backend, Stripe sandbox payments, live URL, write-up).

## Sections still to write
1. Overview, problem, target users, and why AI
2. **Accounts, access and payments** (below)
3. **Professor features** (course setup, materials, guidelines, modes, insights) (below)
4. Student features (tutor, chats, memory)
5. Quality, errors and edge cases
6. Success metrics, risks, milestones

Positioning against Bruin Learn and other LMSs is left open for the pitch. The product is the tutor, so v1 does not add LMS features such as rosters for grading, gradebooks or announcements.

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
