---
paths:
  - "backend/**/*.py"
---

# Backend, Tenancy, Billing & SQL Rules

1. **Tenancy:** Every course-scoped route depends on `get_member`, `get_staff`, or `get_owner`; chat routes also verify `chat.user_id`. Non-members receive `404`; removed or blocked members receive `403`. Roles come exclusively from `memberships`.
2. **Pre-Turn Gates:** Pause windows, student allowances, course AI budget, and app-wide limits are checked in `chats._check_turn_gates` (shared by `post_message`, `post_illustrate`, `assignments.post_turn` and `qna._respond`) before any model call.
3. **Stripe Activation:** Courses activate only through `billing._activate` after signed webhook or server-side Stripe session lookup passes `_pays_for`.
4. **Portable SQL:** Use `?` placeholders, `ON CONFLICT`, and `RETURNING`. Never use SQLite-only functions like `group_concat`. Acquire `db.lock_row` before count-then-insert seat checks.
5. **Production Settings:** Keep `config.check_production_settings` strict.
