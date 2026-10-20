# BruinBuddy — PRD (v1, in progress)

> Status: draft, being written section by section | Last updated: 2026-10-20
> v0 (the deployed class demo) is in [PRD_v0.md](PRD_v0.md). Course requirements and rubric: Capstone "Build an AI Startup" (sign-up and login, AI backend, Stripe sandbox payments, live URL, write-up).

## Sections still to write
1. Overview, problem, target users, and why AI
2. **Accounts, access and payments** (below)
3. Professor features (course setup, materials, guidelines, insights)
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
| **Staff** | Additional professors or TAs, up to the plan's staff cap | Same as owner except billing and deleting the course |
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
- Staff join with a **separate staff code** (or by invitation), limited by the staff cap.
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
- **Staff invitations:** a separate staff code (proposed) or invitations by email?
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
| Course codes, seat cap, rotate, domain restriction, expiry | S | membership model |
| Roster with remove and block | S | membership model |
| Stripe Checkout, webhook, pending-to-active | M | course model |
| Per-student and per-course token caps | S–M | usage logging (exists), membership model |
| Frontend: sign-up, create-course, join, roster screens | M | the above |

Rubric note: sign-up and login, and the Stripe checkout working in production, are listed must-haves in the course requirements.
