# BruinBuddy — Product & UX Design (v1)

> Status: v1 live at https://bruinbuddy.vercel.app since 2026-10-20; checked in a browser locally (desktop and phone width) | Based on [PRD.md](PRD.md) (v1) | Last updated: 2026-10-20
> v0's design (sign-in, chat, one-number dashboard) is in this file's git history. Text only, no wireframe tooling.

## 1. Design principles
- **Teach, don't tell.** No "show answer" button anywhere. What the tutor may reveal is set per problem set by the professor, and the student always sees the rule.
- **Show the sources.** Every claim has a clickable citation; materials students can open are one click away.
- **Label the AI.** Tutor output is marked AI-generated and looks different from course material.
- **Chat is the one place for help.** The course home only launches chats with context attached (PRD §4.1).
- **Fail safe, visibly.** New problem sets start as Graded; limits, pauses and removals say plainly what happened and what to do next, and never fail silently.
- **Aggregates, not surveillance.** Staff never see a student's chats. The UI says so to both sides.

## 2. Information architecture
```
Log in / Sign up / Forgot password / Set new password
   │
   ▼
Home ─┬─ no courses ─────────► Welcome: [Join a course] [Create a course]
      ├─ student in a course ► Course home ──► Chat (sidebar of chats + conversation + source panel)
      └─ owner or staff ─────► Staff console ─ Setup · Materials · Problem sets · AI assignments · Q&A assistant · Guidelines ·
                                               Members · Dashboard · Pause · Plan & limits
                                             └ Preview as student ──► Course home (preview) ──► Chat
Top bar: course switcher · Join or create · name and Log out · About
```
- The **course switcher** lists every course the person belongs to, with their role. The last course used opens by default.
- **Plan & limits** shows seats, the course's token budget and the per-student allowance to all staff; the billing section is shown to the owner only (PRD §2.1: staff can't see billing).
- Routes are hash URLs (`#/c/12`, `#/c/12/chat/40`, `#/c/12/staff/materials`) so links and the back button work.

## 3. Core user flows

**F1. Professor creates and pays for a course.** Sign up → "Create a course" → name, student seats, staff seats, weekly allowance per student → the price updates live from the server → "Pay with Stripe" → Stripe Checkout (test card 4242 4242 4242 4242) → back in the app, the course shows "Confirming payment…" and then the setup checklist. Cancel or failure returns to the plan screen with the course still pending and a "Try payment again" button.

**F2. Setup checklist.** Upload materials → set problem set modes → write guidelines → try it as a student → share the student code. Each step shows done or not done, links to its screen, and stays reachable afterwards. Until there is a ready document the checklist says students will see "not open yet".

**F3. Upload materials.** Materials → "Upload" → pick a category first → choose files → for Solution, tick the problem sets it covers (or "Link later") → tick "I have the right to use these materials" → Upload. Rows appear as *Processing*, then *Ready*, *Failed* (with a reason and Retry) or *No text found*. A yellow note shows any mismatch warning ("Looks like a solution but is tagged as a reading"). Each row can be re-categorised, relinked, replaced or deleted.

**F4. Problem set modes.** Problem sets → one row per set: mode (Graded: hints only · Practice: full help · Solutions open), optional release date, "Tell students if their final answer is correct", linked solutions. New sets show Graded. "Confirm modes" ticks the checklist step.

**F5. Guidelines.** One general guideline (a text box, with starter prompts to click in, or upload a .txt/.md), plus optional additional guidelines, each tagged to one or more materials. Character counters show the caps. A fixed note: guidelines can't unlock solutions, turn off citations or change modes.

**F6. Try it as a student.** "Preview as student" opens the student course home with a banner "Preview: your chats aren't counted in the dashboard." Everything works as for a student.

**F7. Members.** Student code with Copy, Rotate, expiry date and email-domain restriction. Roster with name, email, joined date, questions and tokens, and Remove or Block per student. Owner only: staff list with Remove, "Add staff" (shows a single-use code once, valid 7 days) and pending codes with Revoke.

**F8. Student joins.** Sign up → "Join a course" → enter code → course home. Wrong, rotated or expired code, full course, wrong email domain, pending course and blocked student each get a specific message.

**F9. Student course home.** Course name, pause banner if paused, allowance meter, four entry points, starter questions:
- **Help with a problem set** → pick a set (each labelled with its mode) → a chat opens with the set attached and the rule line visible.
- **Review a topic** → pick a lecture or reading → a chat opens and asks for a review plan for it.
- **Quiz me** → optional topic → a chat opens and the tutor asks the first question.
- **Browse materials** → documents by category; opening one opens the source. Solutions appear only once their set is open.

**F10. Chat.** As in v0 (streaming, numbered citation chips, source panel, AI-generated label, "Used memory"), plus the problem set **rule line** under the title when a set applies ("Problem Set 04 · Graded: hints only"). A set detected mid-chat shows its rule from that reply on. An empty problem set chat lists that set's own problems ("Problem 1", "Problem 2"… with the start of each statement, read from the uploaded file); picking one starts the chat on it. A set without numbered problems asks which problem the student is on.

**F11. Dashboard.** Range selector (7 days · 30 days · Whole term). Panels: usage overview, most-asked materials, unanswered questions, where students are stuck, student usage. Panels that would identify fewer than 5 students show "Not enough students yet to show this without identifying anyone." A "Sample data" badge shows when the course has seeded sample students.

**F13. AI-guided assignment (staff).** Staff console → AI assignments → New assignment → title, problem statement, solution notes → "Auto-generate checkpoints with AI" → edit each checkpoint (title, question, target answer, rubric, hint, points; reorder, add, remove) → "Publish assignment". The list shows started, completed and average score per assignment, with Gradebook (per-student score, per-checkpoint status and tries, expandable transcripts), "Try as student" and Delete.

**F14. AI-guided assignment (student).** Course menu → AI Assignments (`#/c/12/assignments`), also listed under Problem Sets → a card per assignment with progress and score → the workspace (`#/c/12/assignments/3`): left, the problem and a vertical checkpoint stepper (Passed, Active, Skipped, Locked; points; the active question; results of done steps); right, a banner with the active checkpoint, the Socratic chat, "Request hint", "Skip & reveal step (0 pts)" (with a confirm dialog) and the composer. The score sits in the header, with "Your instructor can see this assignment’s conversation and your score." On a phone the two panels stack.

**F15. Ask the course (student).** Course menu → Ask the Course (`#/c/12/qna`). The page has a question box, the topics the staff always answer, the FAQ, and "Your questions" with a status for each (Answered by AI, With course staff, Staff replied, Resolved). A thread (`#/c/12/qna/5`) shows the question and the assistant's answer with its sources (a past Q&A or a page of the materials), plus two buttons: "This answered my question" and "Not satisfied? Ask the course staff" (with an optional note). The thread says who can see it. Staff replies appear in the thread with the staff member's name.

**F16. AI teaching assistant (staff).** Staff console → Q&A assistant, with three views:
- **Inbox:** counts and the escalated threads, waiting ones first. Open one to read it and reply (Send, or Send and mark resolved), then "Save to the knowledge base", with an option to publish it to the FAQ.
- **Knowledge base:** upload Q&A documents (with a rights and privacy confirmation) and see each one's status and pairs found. Below that, the review queue (edit, Approve, Approve all, Delete), the approved pairs with an FAQ toggle, and "Add a Q&A pair".
- **Rules:** the assistant on or off, "Who answers" for each kind of question, and instructions with a character counter.

**F12. Errors and limits** (PRD §4.8): every failure keeps the student's message in the thread and says what to do next — Retry for AI failures; allowance reached with when it frees up; tutor paused with until when; removed or blocked with "contact your instructor"; session expired returns to log in and keeps the draft.

## 4. Key screens

### 4.1 Log in and sign up
```
┌──────────────────────────────────┐
│  BruinBuddy                      │
│  An AI tutor for your course     │
│                                  │
│  [ Continue with Google ]        │  (only if Google is enabled)
│  ───────────── or ─────────────  │
│  Email     [__________________]  │
│  Password  [__________________]  │
│  [ Log in ]                      │
│  Forgot password? · Create account│
└──────────────────────────────────┘
```
Sign up adds a name field. "Forgot password" asks for an email and confirms that a link was sent. The link returns to a "Set a new password" form. In local development the Google button and password reset are hidden.

### 4.2 Create a course
```
┌───────────────────────────────────────────────┐
│ Create a course                               │
│ Course name        [ Stats 100A, Fall 2026 ]  │
│ Student seats      [ 40 ]                     │
│ Staff (TAs, co-instructors) [ 2 ]             │
│ Allowance per student [100k tokens/week ▾]    │
│                    ≈ 25 questions a week      │
│ ───────────────────────────────────────────── │
│ Base                         $19.00           │
│ 2 staff × $9                 $18.00           │
│ 40 seats × $2.00             $80.00           │
│ Total for the term          $117.00           │
│ [ Pay with Stripe ]   Test mode: 4242 4242 …  │
└───────────────────────────────────────────────┘
```

### 4.3 Student course home
```
┌ BruinBuddy   [Stats 100A ▾]                          Alex · Log out ┐
│ ⏸ The tutor is paused for Midterm 1 until Thu 3:00 pm  (if paused)  │
│ Stats 100A                       Allowance this week ▓▓▓▓░░░ 58%    │
│                                                                     │
│ ┌ Help with a problem set ┐ ┌ Review a topic ┐ ┌ Quiz me ┐ ┌ Browse ┐│
│                                                                     │
│ Try asking                                                          │
│ › Why does Bayes' theorem need a prior?                             │
│ › What should I review before the conditional probability quiz?     │
│ › How is variance different from standard deviation?                │
│                                                                     │
│ Recent chats: Bayes and priors · Pset 3 help · Quiz: CLT            │
└─────────────────────────────────────────────────────────────────────┘
```
Empty course: "Your instructor hasn't added materials yet. Check back soon."

### 4.4 Chat screen
```
┌────────────┬─────────────────────────────────────┬──────────────────┐
│ ← Course   │ Pset 4 help                         │ Source           │
│ + New chat │ Problem Set 04 · Graded: hints only │ Class 7 notes    │
│            │                                     │ p. 3             │
│ Pset 4 hlp●│ You: How do I start problem 2?      │ "…posterior ∝    │
│ Bayes      │ BruinBuddy [AI-generated]           │ likelihood ×     │
│ Quiz: CLT  │ What does the problem give you? [1] │ prior…"          │
│            │                                     │ [Open document]  │
│ Alex  ⏻    │ [ Ask a question…             Send ]│                  │
└────────────┴─────────────────────────────────────┴──────────────────┘
```
The empty chat shows the starter questions. On a phone the chat list is a menu and the source panel a bottom sheet.

### 4.5 Staff console
```
┌ BruinBuddy   [Stats 100A ▾ owner]                      Prof. Kim · Log out ┐
│ Setup  Materials  Problem sets  Guidelines  Members  Dashboard  Pause  Plan│
│                                              [ Preview as student ]        │
│ Setup                                                                      │
│ ✓ Upload materials            12 ready, 1 processing                       │
│ ○ Set problem set modes       4 sets, all Graded            [Review modes] │
│ ○ Write guidelines                                          [Write]        │
│ ○ Try it as a student                                       [Preview]      │
│ ○ Share the student code      ABCD-2345  [Copy]                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### 4.6 Materials library
```
│ [ Upload ]                                              Filter: All ▾      │
│ Title                     Category      Status        Linked     Actions   │
│ Class 7 notes             Lecture notes Ready                    ⋯         │
│ Problem Set 04            Problem set   Ready         Sol. 04    ⋯         │
│ Problem Set 04 Solutions  Solution      Ready         Pset 04    ⋯         │
│ scan_week3.pdf            Reading       No text found            ⋯         │
│ ⚠ "week5_answers.pdf" looks like a solution but is tagged as a reading.    │
```

### 4.7 Dashboard
```
│ Dashboard              [7 days | 30 days | Whole term]      Sample data    │
│ Active students 23 · Questions 412 · Seats 31/40 · Tokens 1.2M / 12M       │
│ Questions per day  ▁▂▃▅▇▅▃▂                                                │
│ Most-asked materials          │ Where students are stuck                   │
│ Class 7 notes        61       │ Pset 4   14 students · 3.1 q/student       │
│ Reading 3            44       │          ✓ 9  ◐ 12  ✗ 7                    │
│ Unanswered questions (anonymised)                                          │
│ "Is the midterm cumulative?"                                   Oct 18      │
│ Student usage    Name   Questions   Tokens                                 │
```

## 5. Interaction patterns
**Illustrate studio.** An "✨ Illustrate" button in the chat sidebar (and under tutor replies) opens the right-hand Illustration Studio, automatically choosing between an interactive isometric apparatus (`wheresryan22/anatomy`), a 3Blue1Brown-style math animation (`adithya-s-k/manim_skill`), or a progressive diagram/whiteboard explainer (`iart-ai/explainer-video-skills`), rendered in-page with one-click downloads (`.html`, `.webm`, `.png`, `.svg`, `.py`).

**Citations.** Numbered chips at the end of the claim; click opens the passage in the source panel with document, page and an "Open document" link (signed, expires quickly). Solutions are never cited or linked until released.

**Rule line.** Under the chat title: "Problem Set 04 · Graded: hints only", "Practice: full help" or "Solutions open". The same labels are used on the course home picker and in the staff Problem sets screen, so students and staff see one vocabulary.

**Teaching responses.** Hints as short steps, ending with a question when it helps. A refusal is one sentence and then the next hint, with no lecture.

**AI label.** On every tutor message. The About page states that the tutor can make mistakes, credits MIT OCW for the demo course, and says staff see aggregate usage and not individual chats.

**Memory.** "Used memory from past chats" under a reply that used it. Memory is per course. Not viewable or editable in v1.

**Allowance.** A meter on the course home ("58% of this week's allowance used"). At the limit the reply slot says "You've used this week's allowance. More frees up Tue 9:40 am." and nothing is sent to the AI.

**Pause.** A banner on the home and chat while paused, with the professor's message and the end time. Sending shows the same message.

**Loading and errors.** Typing indicator and streaming as in v0. Every request failure keeps the student's message and offers Retry where retrying can help. Payment, upload and save errors appear inline next to the control that caused them.

**Copy and codes.** Codes are shown in a monospace box with a Copy button. A staff code is shown once with "Copy it now; you won't see it again."

## 6. Visual design system
- **Type:** system sans-serif; 16px body with generous line height; monospace only for codes.
- **Layout:** chat column max ~720px; staff screens max ~1100px with tables that scroll horizontally on small screens.
- **Color:** neutral light and dark themes following the system setting, one green accent for buttons, chips and focus; amber for warnings, red for errors. No UCLA blue or gold, no UCLA marks.
- **Components:** button (primary, secondary, danger, link), text input, select, checkbox, card, tabs, table, badge (role, status, mode), banner (info, warning), meter, modal, citation chip, message bubble, source panel.
- **Math:** KaTeX inline and block, in answers and source excerpts.
- **Responsive:** usable on a phone (PRD §4.7): the chat list becomes a menu, the source panel a bottom sheet, staff tabs scroll horizontally, tables scroll inside their card.

## 7. Accessibility
- Keyboard: Enter sends, Shift+Enter adds a line; all controls reachable with Tab; visible focus rings.
- Contrast at least 4.5:1; status is never shown by color alone (badges carry text).
- Citation chips have labels ("Source 1: Class 7 notes, page 3"). Math renders with KaTeX's MathML.
- New tutor messages are announced (polite live region); form errors use `role="alert"`.

## 8. Design decisions and open questions
| Decision | Choice | Alternative | Why |
|---|---|---|---|
| Student surface | Course home that launches chats | Separate quiz, planner and flashcard tools | PRD §4.1: chat is the one place for help |
| Staff surface | One console with tabs | A wizard only | The checklist guides setup; tabs make every step revisitable |
| Code entry | One "Enter a course code" field for students and staff | Separate fields | Less to explain; the server knows which is which |
| Price display | Server-computed breakdown that updates as the plan changes | A fixed price table | The formula (PRD §2.7) lives in one place on the server, so it can change without a frontend release |
| Problem set rule | Always-visible rule line | A tooltip | Students should never be surprised by a refusal |
| Dashboard privacy | Small groups hidden, no names in unanswered list | Full per-student detail | PRD §3.6 |
| Routing | Hash URLs | History API with rewrites | Works on Vercel and the local backend unchanged |

**Open questions**
- Do students need to see and clear their memory? (Out of scope for v1.)
- Should staff be able to edit starter questions? (Out of scope for v1.)
- Do we need a "report a wrong answer" control? (Out of scope for v1.)


## 9. UCLA Bruin Learn (Canvas LMS) UI & Accessibility Suite
- **UCLA Blue Global Navigation Rail (`CanvasShell.jsx`):** Fixed `84px` UCLA Blue (`#1e6b9e`) left rail with `UCLA` wordmark, `Account`, `Dashboard` (`#/dashboard` with multi-course timeline & mountain/pine-tree line-art footer), `Courses` slide-out tray, `History` slide-out tray, `Illustrate` launcher, `Search` tray, `Accessibility` drawer, and `Help`.
- **Course Home Hero Banner & Accordions (`CourseHome.jsx`):** UCLA Blue & Gold (`#ffd100`) course hero card, `Welcome` and `Modules` gold-underlined headings, collapsible gray accordion bars, `SHOW BY DATE` / `SHOW BY TYPE` filterable assignment & module groups, and a right-hand `To do` & Allowance stream.
- **Appearance & Accessibility Engine (`accessibility.jsx`):**
  - **Themes:** Light (UCLA Bruin Learn), Dark (Westwood Night), High Contrast (WCAG AAA), and System Auto.
  - **Colorblind Modes:** Standard, Protanopia/Deuteranopia (Red-Green Safe Okabe-Ito tokens), Tritanopia (Blue-Yellow Safe), and Monochromacy.
  - **Dyslexia & Reading Comfort:** Dyslexia-friendly typography & spacing mode, reading surface paper tints (`Cream`, `Sage`, `Sky`), font scaling (`100%`–`130%`), link underlining, reduced motion, and built-in **`📖 Immersive Reader`** with Text-to-Speech (`speechSynthesis`), Line Focus, and Syllable spacing.
