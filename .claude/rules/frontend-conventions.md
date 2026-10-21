---
paths:
  - "frontend/**/*"
---

# Frontend Architecture & Isolation Rules

1. **Centralized HTTP Client:** All HTTP calls and SSE streams must go through `frontend/src/api.js` (never raw `fetch` in components).
2. **Hash Routing:** All routes use hash URLs managed by `frontend/src/router.js`.
3. **Student / Staff Isolation:** Student components (`CourseHome.jsx`, `ChatView.jsx`, `Message.jsx`) must never load staff-only endpoints or staff-scoped file links.
4. **Build Verification:** Run `cd frontend && npm run build` after any frontend change to confirm clean compilation.
