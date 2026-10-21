# BruinBuddy — Product & UX Design (v1)

> Status: v1, being built on branch `v1-build` | Based on [PRD.md](PRD.md) (v1) | Last updated: 2026-10-20
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
      └─ owner or staff ─────► Staff console ─ Setup · Materials · Problem sets · Guidelines ·
                                               Members · Dashboard · Pause · Plan (owner)
                                             └ Preview as student ──► Course home (preview) ──► Chat
Top bar: course switcher · Join or create · name and Log out · About
```
- The **course switcher** lists every course the person belongs to, with their role. The last course used opens by default.
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

**F10. Chat.** As in v0 (streaming, numbered citation chips, source panel, AI-generated label, "Used memory"), plus the problem set **rule line** under the title when a set applies ("Problem Set 04 · Graded: hints only"). A set detected mid-chat shows its rule from that reply on.

**F11. Dashboard.** Range selector (7 days · 30 days · Whole term). Panels: usage overview, most-asked materials, unanswered questions, where students are stuck, student usage. Panels that would identify fewer than 5 students show "Not enough students yet to show this without identifying anyone." A "Sample data" badge shows when the course has seeded sample students.

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
| Price display | Server-computed breakdown that updates as the plan changes | A fixed price table | The formula is still open (PRD §2.7) and stays in one place |
| Problem set rule | Always-visible rule line | A tooltip | Students should never be surprised by a refusal |
| Dashboard privacy | Small groups hidden, no names in unanswered list | Full per-student detail | PRD §3.6 |
| Routing | Hash URLs | History API with rewrites | Works on Vercel and the local backend unchanged |

**Open questions**
- Do students need to see and clear their memory? (Out of scope for v1.)
- Should staff be able to edit starter questions? (Out of scope for v1.)
- Do we need a "report a wrong answer" control? (Out of scope for v1.)
