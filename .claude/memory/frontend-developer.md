# Memory — `frontend-developer`

*Last updated: 2026-10-20*

## 1. Frontend Architecture (`frontend/src/`)
- **Boot & Routing (`App.jsx`, `router.js`):**
  - Fetches `/api/config` on startup to determine auth mode (`supabase` vs local) and Stripe settings.
  - Uses hash-based routing (`router.js`) for seamless SPA navigation across FastAPI static serving and Vercel.
- **HTTP & Streaming (`api.js`, `auth.js`):**
  - All backend calls go through `frontend/src/api.js` (attaches Bearer token, handles JSON & SSE streaming for chat messages).
  - Never call `fetch` directly in React components.
- **Student Experience (`CourseHome.jsx`, `ChatView.jsx`, `Message.jsx`):**
  - Supports General, Review, and Quiz chat modes, starter questions, allowance indicator, and clickable source citations.
  - Must **never** load or display staff-only endpoints, staff-scoped file URLs, or solution text.
- **Staff Console (`frontend/src/staff/`):**
  - `StaffConsole.jsx` coordinates tabs: `Setup.jsx`, `Materials.jsx`, `ProblemSets.jsx`, `Guidelines.jsx`, `Pause.jsx`, `Members.jsx`, `Dashboard.jsx`, and `Plan.jsx`.
  - `Dashboard.jsx` renders aggregate course usage and topic analytics while respecting the backend small-group privacy threshold.
- **Verification:**
  - Always run `cd frontend && npm run build` after any JSX/CSS change.
