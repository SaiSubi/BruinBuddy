# BruinBuddy — Product & UX Design (v0)

> Status: v0 | Based on [PRD.md](PRD.md) v0 | Last updated: 2026-10-19
> Scope: a local web app with a sign-in, a chat screen, and a one-number professor dashboard. Text only, no wireframe tooling.

## 1. Design principles
- **Teach, don't tell.** The tutor asks and hints. The interface never offers a "show answer" button, because v0 has no escape hatch.
- **Show the sources.** Every claim has a visible, clickable citation.
- **Label the AI.** Tutor output is marked AI-generated and is visually distinct from course material.
- **Keep it small.** v0 has three screens, and the chat screen does nearly all the work.

## 2. Information architecture
```
Sign-in  ──►  Student:    Chat screen (chat list + conversation + source panel)
         └─►  Professor:  Dashboard (question count)
```
- **Sign-in** is a name and a role (student or professor). There is no password.
- **Student** has one main screen. The chat list is a sidebar, not a separate page.
- **Professor** has one page: the dashboard.
- **Navigation** is just the signed-in name, a sign-out link, and an About link for MIT OCW attribution.

## 3. Core user flows

**F1. First visit.** Sign in as a student, land on an empty new chat with a short welcome and three suggested questions. Ask a question, get a cited answer.

**F2. Ask a concept question.** Type a question, the answer appears with numbered citations, click a citation to see the source passage in the side panel, then continue the conversation.

**F3. Ask for an assigned problem's answer.** Paste a problem set problem and ask for the answer. The tutor asks what the student has tried and gives a hint. If the student asks again, the tutor holds the line and gives a bigger hint, never the answer.

**F4. Not in the materials.** The tutor says it can't find this in the course materials and suggests what it can help with.

**F5. Multiple chats.** Click "New chat" to start another, click a chat in the sidebar to reopen it. History survives a restart.

**F6. Memory.** Start a new chat after discussing a topic earlier. The tutor refers back to it naturally, and a small note shows that memory was used.

**F7. Professor.** Sign in as a professor and see the total question count.

## 4. Key screens

### 4.1 Sign-in
```
┌──────────────────────────────┐
│  BruinBuddy                  │
│  Study help for 18.05        │
│                              │
│  Name  [________________]    │
│  I am  (•) Student ( ) Prof. │
│                              │
│  [ Continue ]                │
└──────────────────────────────┘
```
Same name plus role returns to the same history and memory.

### 4.2 Student chat screen
```
┌────────────┬─────────────────────────────────┬──────────────────┐
│ + New chat │  Bayes and priors               │ Source           │
│            │                                 │                  │
│ Bayes and  │  You                            │ Class 7 notes    │
│  priors  ● │  Why does Bayes need a prior?   │ p. 3             │
│ Pset 3 hlp │                                 │ ──────────────── │
│ Exam prep  │  BruinBuddy        [AI-generated]│ "…posterior ∝    │
│            │  Bayes' theorem combines…  [1]  │ likelihood ×     │
│            │  The prior encodes…        [2]  │ prior…"          │
│            │                                 │                  │
│            │  Used memory: you were reviewing│ [ Open document ]│
│            │  conditional probability        │                  │
│            │                                 │                  │
│ Alex   ⏻   │  [ Ask a question…        Send ]│                  │
└────────────┴─────────────────────────────────┴──────────────────┘
```
- **Left sidebar:** New chat button, list of chats (most recent first, titled automatically from the first question), the signed-in name, and sign-out.
- **Center:** the conversation, with the input fixed at the bottom.
- **Right panel:** the source viewer. It is empty until a citation is clicked, and it collapses on narrow screens.
- **Empty state:** a welcome line plus three suggested questions (concept, study plan, "I'm stuck on a problem").

### 4.3 Professor dashboard
```
┌──────────────────────────────────────┐
│ BruinBuddy · Professor        Sign out│
│                                      │
│   Questions asked                    │
│        128                           │
└──────────────────────────────────────┘
```
One big number. No filters, no charts in v0.

## 5. Interaction patterns

**Citations**
- Inline numbered chips such as [1] sit at the end of the claim they support.
- Clicking a chip opens the source panel with the document name, location (page or section), and the passage the answer used.
- "Open document" opens the full source file in a new tab.
- Solution documents never appear as a citation, a source, or a link.

**Teaching responses**
- Hints come as short steps. Each reply ends with a question back to the student when it makes sense ("What is P(A | B) here?").
- When the tutor declines to give an answer, it says so briefly and offers the next hint. It does not lecture about academic integrity.
- There is no "just show me" button and no way to unlock solutions.

**AI label**
- Every tutor message carries an "AI-generated" tag. Student messages do not.
- The About page states that the tutor can make mistakes and that the materials are from MIT OCW 18.05, CC BY-NC-SA 4.0.

**Memory**
- When a reply uses memory, a small line under it says what it drew on ("Used memory: you were reviewing conditional probability").
- v0 does not let students view, edit, or clear memory (PRD §8).

**Loading and errors**
- While the tutor responds, show a typing indicator and stream text as it arrives.
- If the request fails, show "Something went wrong. Try again" with a retry button, and keep the student's message in the box.
- If no relevant sources are found, show the "not in the materials" reply, with no citations.
- Long pasted problems are accepted, and the input grows up to a limit and then scrolls.

## 6. Visual design system
- **Type:** one system sans-serif font. Body text 16px with generous line height, because answers are long.
- **Layout:** a centered chat column with a maximum width of about 720px so lines stay readable.
- **Color:** a neutral light theme with one accent color for buttons and citation chips. Tutor messages sit on a faint tinted background to set them apart from student messages. Use no UCLA blue or gold, and no UCLA marks.
- **Components:** message bubble, citation chip, source panel, chat list item, primary and secondary buttons, text input.
- **Math:** render formulas with KaTeX, both inline and block, in tutor answers and source excerpts.
- **Responsive:** desktop first. On narrow screens the sidebar collapses to a menu and the source panel becomes a slide-up sheet. Not optimized beyond that.

## 7. Accessibility and usability
- Everything works with the keyboard: Enter sends, Shift+Enter adds a new line, Tab reaches citation chips, and Enter opens one.
- Text contrast of at least 4.5:1, and focus rings on all controls.
- Citation chips have a text label (for example "Source 1: Class 7 notes, p. 3") for screen readers.
- Math renders with accessible markup (KaTeX's MathML output), not images.
- New tutor messages are announced to screen readers (a polite live region).
- Informal usability check: have two or three classmates try F1–F5 and note where they get stuck. No formal testing in v0.

## 8. Design decisions and open questions

| Decision | Choice | Alternative | Why |
|---|---|---|---|
| Screens | Three: sign-in, chat, dashboard | Separate pages for chats, memory, and settings | Smallest thing that covers the PRD |
| Citations | Numbered chips plus a side panel | Footnotes at the end of the message | Lets students check a claim without losing their place |
| Chat list | Sidebar in the chat screen | Separate "My chats" page | Switching chats is frequent |
| Refusals | Short, then a hint | A long explanation of the policy | Keeps the student working on the problem |
| Memory visibility | A one-line note only | A memory page with edit and delete | Out of v0 scope |
| Dashboard | One number | Charts and a topic breakdown | PRD v0 |

**Open questions**
- Do we auto-title chats with the model or just use the first question's text? (Cheaper: first words of the first question.)
- Should the suggested questions be fixed or drawn from the materials?
- Does the source panel need to show the original PDF page, or is the extracted text enough? (Depends on how well math extracts; see TECHNICAL.md.)
- Do students need a way to report a wrong answer? Deferred.
