# Memory — `frontend-developer`

*Last updated: 2026-10-20*

## 1. Frontend Architecture (`frontend/src/`)
- **Boot & Routing (`App.jsx`, `router.js`):**
  - Fetches `/api/config` on startup to determine auth mode (`supabase` vs local) and Stripe settings.
  - Wraps the application in `<AccessibilityProvider>` (`frontend/src/accessibility.jsx`) and `<CanvasShell>` (`frontend/src/CanvasShell.jsx`).
  - Uses hash-based routing (`router.js`) for seamless SPA navigation across FastAPI static serving and Vercel (`#/dashboard`, `#/c/:id`, `#/c/:id/chat/:chatId`, `#/c/:id/staff/:tab`).
- **UCLA Bruin Learn (Canvas LMS) Shell (`CanvasShell.jsx`, `CourseHome.jsx`, `styles.css`):**
  - **Global Left Navigation Rail (`84px`, `#1e6b9e` UCLA Blue):** `UCLA` wordmark, `Account` (avatar with UCLA Gold ring), `Dashboard` (multi-course activity stream + mountain/pine-tree line-art SVG footer), `Courses` slide-out tray, `History` slide-out tray, `Illustrate` studio launcher, `Search` tray, `Accessibility` tray, and `Help`. Active rail items turn white (`#ffffff`) with UCLA Blue text.
  - **Course Sub-Navigation & Hero Card (`CourseHome.jsx`):** Collapsible left course menu (`Home`, `Syllabus & AI Rules`, `Assignments`, `Modules & Files`, `AI Tutor Notebook`, `✨ Illustrate Studio`, plus `Instructor Console` links for staff) with the Canvas vertical dark bar active indicator. Center column features the **UCLA Blue & Gold Hero Card** (`#1e6b9e` header, `#ffd100` gold line & pill badge, `Welcome` and `Modules` gold-underlined headings, collapsible gray accordion bars, and `SHOW BY DATE` / `SHOW BY TYPE` filterable assignment/module groups) and a right-hand `To do` / Allowance stream.
- **Appearance & Accessibility Engine (`accessibility.jsx`):**
  - Persists preferences in `localStorage` (`bb_a11y_prefs`) and synchronizes root `data-theme`, `data-colorblind`, `data-dyslexia`, `data-paper-tint`, `data-font-scale`, `data-underline-links`, and `data-reduced-motion` attributes on `<html>`.
  - Supports **Themes** (`light`, `dark`, `high-contrast`, `system`), **Colorblind Modes** (`none`, `protanopia`, `deuteranopia`, `tritanopia`, `monochrome`), **Dyslexia-Friendly Typography & Paper Tints** (`cream`, `sage`, `sky`), **Font Scaling** (`100%`–`130%`), and the **`📖 Immersive Reader`** modal with Text-to-Speech (`window.speechSynthesis`), Line Focus, and Syllable spacing.
- **HTTP & Streaming (`api.js`, `auth.js`):**
  - All backend calls go through `frontend/src/api.js` (attaches Bearer token, handles JSON, SSE streaming for chat messages, and `api.illustrate` / `api.illustrations` / `api.downloadIllustration`).
  - Never call `fetch` directly in React components.
- **Student Experience (`CourseHome.jsx`, `ChatView.jsx`, `Message.jsx`, `IllustratePane.jsx`):**
  - Supports General, Review, and Quiz chat modes, starter questions, allowance indicator, clickable source citations, and the **✨ Illustrate** sidebar studio (`IllustratePane.jsx`).
  - Must **never** load or display staff-only endpoints, staff-scoped file URLs, or solution text.
- **Verification:**
  - Always run `cd frontend && npm run build` after any JSX/CSS change.
