import { useEffect, useState } from 'react'
import { useAccessibility, AccessibilityPanel } from './accessibility.jsx'
import { api } from './api.js'
import { day, ROLE } from './format.js'
import { navigate } from './router.js'
import { Badge } from './ui.jsx'

// Clean monochrome stroke SVG icons matching Instructure Canvas / UCLA Bruin Learn
export function RailIcon({ name, size = 22 }) {
  switch (name) {
    case 'dashboard':
      return (
        <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.8">
          <path d="M4 15a8 8 0 1 1 16 0" strokeLinecap="round" />
          <path d="M12 15l3.5-4.5" strokeLinecap="round" />
          <circle cx="12" cy="15" r="1.5" fill="currentColor" />
          <path d="M4 18h16" strokeLinecap="round" />
        </svg>
      )
    case 'courses':
      return (
        <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.8">
          <path d="M5 4h12a2 2 0 0 1 2 2v14H7a2 2 0 0 1-2-2V4z" />
          <path d="M5 17h14" />
          <path d="M9 8h6M9 11.5h4" strokeLinecap="round" />
        </svg>
      )
    case 'history':
      return (
        <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.8">
          <circle cx="12" cy="12" r="8.5" />
          <path d="M12 7.5v5l3.2 2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      )
    case 'illustrate':
      return (
        <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.8">
          <polygon points="5 3 19 12 5 21 5 3" strokeLinejoin="round" />
        </svg>
      )
    case 'search':
      return (
        <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.8">
          <circle cx="10.8" cy="10.8" r="6.5" />
          <path d="M15.8 15.8L20.5 20.5" strokeLinecap="round" />
        </svg>
      )
    case 'a11y':
      return (
        <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.8">
          <circle cx="12" cy="12" r="9" />
          <circle cx="12" cy="7.5" r="1.3" fill="currentColor" />
          <path d="M7.5 10.5h9M12 10.5v4.2m0 0l-2.3 3.8m2.3-3.8l2.3 3.8" strokeLinecap="round" />
        </svg>
      )
    case 'help':
      return (
        <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.8">
          <circle cx="12" cy="12" r="8.5" />
          <path d="M9.6 9.4a2.5 2.5 0 1 1 3.7 2.2c-.8.5-1.3 1-1.3 1.9" strokeLinecap="round" />
          <circle cx="12" cy="16.8" r="0.9" fill="currentColor" />
        </svg>
      )
    case 'reader':
      return (
        <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.8">
          <path d="M2 5.5C2 4.7 2.7 4 3.5 4H10c1.1 0 2 .9 2 2v13.5c0-.8-.7-1.5-1.5-1.5H3.5C2.7 18 2 17.3 2 16.5v-11z" />
          <path d="M22 5.5c0-.8-.7-1.5-1.5-1.5H14c-1.1 0-2 .9-2 2v13.5c0-.8.7-1.5 1.5-1.5h6.5c.8 0 1.5-.7 1.5-1.5v-11z" />
        </svg>
      )
    case 'doc':
      return (
        <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.8">
          <path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
          <polyline points="14 3 14 9 20 9" />
          <line x1="8" y1="13" x2="16" y2="13" />
          <line x1="8" y1="17" x2="13" y2="17" />
        </svg>
      )
    case 'assignment':
      return (
        <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.8">
          <rect x="4" y="3" width="16" height="18" rx="2" />
          <line x1="8" y1="8" x2="16" y2="8" />
          <line x1="8" y1="12" x2="16" y2="12" />
          <line x1="8" y1="16" x2="12" y2="16" />
        </svg>
      )
    case 'chat':
      return (
        <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.8">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      )
    default:
      return null
  }
}

export function courseCodeTag(name = '', id = 1) {
  const trimmed = name.trim()
  const codeMatch = trimmed.match(/^([A-Z]{2,8}\s*[- ]?\s*\d{1,4}[A-Z]?)/i)
  if (codeMatch) return `26F-${codeMatch[1].toUpperCase().replace(/\s+/g, '')}-LEC-1`
  const words = trimmed.split(/\s+/).filter(Boolean)
  const prefix = words
    .slice(0, 2)
    .map((w) => w.replace(/[^A-Za-z0-9]/g, '').slice(0, 4).toUpperCase())
    .join('')
  return `26F-${prefix || 'BRUIN'}-${100 + (Number(id) % 899)}-LEC-1`
}

export default function CanvasShell({
  me,
  course = null,
  courseId = null,
  activeSection = 'home', // 'dashboard' | 'home' | 'chat' | 'assignments' | 'modules' | 'syllabus' | 'staff' | 'join' | 'create' | 'about'
  staffTab = null,
  breadcrumb = null,
  onLogOut,
  onSelectCourseSection = null,
  fullHeight = false,
  children,
}) {
  const [activeTray, setActiveTray] = useState(null) // 'account' | 'courses' | 'history' | 'search' | 'a11y' | null
  const [subNavOpen, setSubNavOpen] = useState(true)
  const [railCompact, setRailCompact] = useState(false)
  const [trayChats, setTrayChats] = useState([])
  const [searchQuery, setSearchQuery] = useState('')
  const { activeBadgeCount, openImmersiveReader, prefs, updatePref } = useAccessibility()

  const resolvedCourseId = course?.id || courseId || me?.courses?.[0]?.id || null

  useEffect(() => {
    if (resolvedCourseId && (activeTray === 'history' || activeTray === 'search')) {
      api.chats(resolvedCourseId).then(setTrayChats).catch(() => {})
    }
  }, [resolvedCourseId, activeTray])

  const toggleTray = (name) => {
    setActiveTray((prev) => (prev === name ? null : name))
  }

  const closeTray = () => setActiveTray(null)

  const openChatOrNew = async (courseObj, illustrate = false) => {
    const cid = courseObj?.id || resolvedCourseId
    if (!cid) {
      navigate('/join')
      return
    }
    try {
      const list = await api.chats(cid)
      if (list && list.length > 0) {
        if (illustrate) {
          try { sessionStorage.setItem(`bb_open_illustrate_${list[0].id}`, '1') } catch { /* ignore */ }
        }
        navigate(`/c/${cid}/chat/${list[0].id}`)
        return
      }
      const created = await api.newChat(cid, 'chat', null)
      if (illustrate) {
        try { sessionStorage.setItem(`bb_open_illustrate_${created.id}`, '1') } catch { /* ignore */ }
      }
      navigate(`/c/${cid}/chat/${created.id}`)
    } catch {
      navigate(`/c/${cid}`)
    }
  }

  const handleHeaderSearch = (e) => {
    e.preventDefault()
    if (!searchQuery.trim()) return
    setActiveTray('search')
  }

  const initials = (me?.name || 'Bruin')
    .split(/\s+/)
    .map((p) => p[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  const isStaff = course && (course.role === 'owner' || course.role === 'staff')
  const codeLabel = course ? courseCodeTag(course.name, course.id) : null

  return (
    <div className={`canvas-shell ${fullHeight ? 'canvas-shell-fixed' : ''} ${railCompact ? 'rail-compact' : ''}`}>
      {/* 1. UCLA Blue Global Left Navigation Rail (Screenshots 1–4) */}
      <aside className="canvas-rail" aria-label="UCLA Bruin Learn Global Navigation">
        <a
          className="ucla-brand-logo"
          href="#/"
          onClick={() => closeTray()}
          aria-label="UCLA BruinBuddy Home"
        >
          UCLA
        </a>

        <button
          type="button"
          className={`rail-item ${activeTray === 'account' ? 'active' : ''}`}
          onClick={() => toggleTray('account')}
          aria-expanded={activeTray === 'account'}
        >
          <span className="rail-avatar" aria-hidden="true">{initials}</span>
          <span className="rail-label">Account</span>
        </button>

        <button
          type="button"
          className={`rail-item ${activeSection === 'dashboard' && !activeTray ? 'active' : ''}`}
          onClick={() => {
            closeTray()
            navigate('/dashboard')
          }}
        >
          <RailIcon name="dashboard" size={24} />
          <span className="rail-label">Dashboard</span>
        </button>

        <button
          type="button"
          className={`rail-item ${activeTray === 'courses' || (activeSection !== 'dashboard' && activeSection !== 'about' && !activeTray) ? 'active' : ''}`}
          onClick={() => toggleTray('courses')}
          aria-expanded={activeTray === 'courses'}
        >
          <RailIcon name="courses" size={24} />
          <span className="rail-label">Courses</span>
        </button>

        <button
          type="button"
          className={`rail-item ${activeTray === 'history' ? 'active' : ''}`}
          onClick={() => toggleTray('history')}
          aria-expanded={activeTray === 'history'}
        >
          <RailIcon name="history" size={24} />
          <span className="rail-label">History</span>
        </button>

        <button
          type="button"
          className="rail-item"
          onClick={() => {
            closeTray()
            openChatOrNew(course, true)
          }}
          title="Open Illustrate Animation Studio"
        >
          <RailIcon name="illustrate" size={22} />
          <span className="rail-label">Illustrate</span>
        </button>

        <button
          type="button"
          className={`rail-item ${activeTray === 'search' ? 'active' : ''}`}
          onClick={() => toggleTray('search')}
          aria-expanded={activeTray === 'search'}
        >
          <RailIcon name="search" size={24} />
          <span className="rail-label">Search</span>
        </button>

        <button
          type="button"
          className={`rail-item ${activeTray === 'a11y' ? 'active' : ''}`}
          onClick={() => toggleTray('a11y')}
          aria-expanded={activeTray === 'a11y'}
        >
          <span className="rail-icon-wrap">
            <RailIcon name="a11y" size={24} />
            {activeBadgeCount > 0 && <span className="rail-badge">{activeBadgeCount}</span>}
          </span>
          <span className="rail-label">Accessibility</span>
        </button>

        <button
          type="button"
          className={`rail-item ${activeSection === 'about' && !activeTray ? 'active' : ''}`}
          onClick={() => {
            closeTray()
            navigate('/about')
          }}
        >
          <RailIcon name="help" size={24} />
          <span className="rail-label">Help</span>
        </button>

        <div className="rail-spacer" />

        <button
          type="button"
          className="rail-collapse-btn"
          onClick={() => setRailCompact((v) => !v)}
          aria-label={railCompact ? 'Expand global navigation' : 'Collapse global navigation'}
          title={railCompact ? 'Expand navigation rail' : 'Collapse navigation rail'}
        >
          {railCompact ? '→|' : '|←'}
        </button>
      </aside>

      {/* 2. Slide-Out White Tray (Screenshot 2) */}
      {activeTray && (
        <>
          <div className="canvas-tray-backdrop" onClick={closeTray} aria-hidden="true" />
          <aside
            className={`canvas-tray ${activeTray === 'a11y' ? 'canvas-tray-wide' : ''}`}
            role="dialog"
            aria-label={`${activeTray} drawer`}
          >
            <div className="canvas-tray-head">
              <h2>
                {activeTray === 'courses' && 'Courses'}
                {activeTray === 'account' && me?.name}
                {activeTray === 'history' && 'Recent Study History'}
                {activeTray === 'search' && 'Search Courses & Chats'}
                {activeTray === 'a11y' && 'Appearance & Accessibility'}
              </h2>
              <button type="button" className="canvas-tray-close" onClick={closeTray} aria-label="Close tray">
                ×
              </button>
            </div>
            <hr className="canvas-tray-hr" />

            {activeTray === 'courses' && (
              <div className="canvas-tray-body">
                <p className="canvas-tray-top-link">
                  <a
                    href="#/dashboard"
                    onClick={() => {
                      closeTray()
                    }}
                  >
                    All courses (Dashboard)
                  </a>
                </p>
                <hr className="canvas-tray-hr" />
                {me?.courses?.length ? (
                  <ul className="canvas-course-tray-list">
                    {me.courses.map((c) => (
                      <li key={c.id}>
                        <a
                          href={`#/c/${c.id}`}
                          className="canvas-tray-course-link"
                          onClick={() => closeTray()}
                        >
                          {courseCodeTag(c.name, c.id)} {c.name}
                        </a>
                        <div className="muted small">
                          Term: 2026 Fall Quarter
                          {c.role !== 'student' ? ` · ${ROLE[c.role]}` : ''}
                          {c.status === 'pending' ? ' · Pending payment' : ''}
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="muted">You haven’t joined a course yet.</p>
                )}
                <div className="canvas-tray-actions">
                  <button
                    type="button"
                    className="primary small"
                    onClick={() => {
                      closeTray()
                      navigate('/join')
                    }}
                  >
                    + Join or create a course
                  </button>
                </div>
                <p className="muted small canvas-tray-note">
                  Welcome to your courses! Click any course above to open its AI Tutor, Illustrate Studio, and course materials.
                </p>
              </div>
            )}

            {activeTray === 'account' && (
              <div className="canvas-tray-body">
                <div className="account-tray-profile">
                  <div className="account-avatar-large">{initials}</div>
                  <div>
                    <strong>{me?.name}</strong>
                    <div className="muted small">{me?.email || 'UCLA Bruin Learn Account'}</div>
                  </div>
                </div>
                <hr className="canvas-tray-hr" />
                <div className="account-quick-theme">
                  <span className="small muted">Quick Theme Switch:</span>
                  <div className="segmented">
                    <button
                      type="button"
                      className={prefs.theme === 'light' ? 'active' : ''}
                      onClick={() => updatePref('theme', 'light')}
                    >
                      Light
                    </button>
                    <button
                      type="button"
                      className={prefs.theme === 'dark' ? 'active' : ''}
                      onClick={() => updatePref('theme', 'dark')}
                    >
                      Dark
                    </button>
                    <button
                      type="button"
                      className={prefs.theme === 'high-contrast' ? 'active' : ''}
                      onClick={() => updatePref('theme', 'high-contrast')}
                    >
                      High Contrast
                    </button>
                  </div>
                </div>
                <ul className="canvas-course-tray-list">
                  <li>
                    <button
                      type="button"
                      className="link"
                      onClick={() => setActiveTray('a11y')}
                    >
                      Appearance & Accessibility Settings
                    </button>
                  </li>
                  <li>
                    <a href="#/join" onClick={closeTray}>
                      Join or create a course
                    </a>
                  </li>
                  <li>
                    <a href="#/about" onClick={closeTray}>
                      About BruinBuddy & Academic Integrity
                    </a>
                  </li>
                </ul>
                <hr className="canvas-tray-hr" />
                <button type="button" className="secondary" onClick={onLogOut}>
                  Log out
                </button>
              </div>
            )}

            {activeTray === 'history' && (
              <div className="canvas-tray-body">
                <div className="row-between">
                  <span className="muted small">
                    {course ? course.name : 'Recent conversations'}
                  </span>
                  {resolvedCourseId && (
                    <button
                      type="button"
                      className="primary small"
                      onClick={async () => {
                        closeTray()
                        const created = await api.newChat(resolvedCourseId)
                        navigate(`/c/${resolvedCourseId}/chat/${created.id}`)
                      }}
                    >
                      + New chat
                    </button>
                  )}
                </div>
                <hr className="canvas-tray-hr" />
                {trayChats.length > 0 ? (
                  <ul className="canvas-course-tray-list">
                    {trayChats.slice(0, 20).map((ch) => (
                      <li key={ch.id}>
                        <a
                          href={`#/c/${resolvedCourseId}/chat/${ch.id}`}
                          className="canvas-tray-course-link"
                          onClick={closeTray}
                        >
                          {ch.title}
                        </a>
                        <div className="muted small">
                          {day(ch.updated_at)} {ch.kind !== 'chat' ? `· ${ch.kind}` : ''}
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="muted small">No recent chats yet in this course.</p>
                )}
              </div>
            )}

            {activeTray === 'search' && (
              <div className="canvas-tray-body">
                <input
                  type="search"
                  placeholder="Filter courses or chats…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  autoFocus
                />
                <h3 className="section-title">Courses</h3>
                <ul className="canvas-course-tray-list">
                  {(me?.courses || [])
                    .filter((c) => !searchQuery || c.name.toLowerCase().includes(searchQuery.toLowerCase()))
                    .map((c) => (
                      <li key={c.id}>
                        <a href={`#/c/${c.id}`} onClick={closeTray}>
                          {courseCodeTag(c.name, c.id)} {c.name}
                        </a>
                      </li>
                    ))}
                </ul>
                {trayChats.length > 0 && (
                  <>
                    <h3 className="section-title">Chats in Current Course</h3>
                    <ul className="canvas-course-tray-list">
                      {trayChats
                        .filter((ch) => !searchQuery || ch.title.toLowerCase().includes(searchQuery.toLowerCase()))
                        .slice(0, 12)
                        .map((ch) => (
                          <li key={ch.id}>
                            <a href={`#/c/${resolvedCourseId}/chat/${ch.id}`} onClick={closeTray}>
                              {ch.title}
                            </a>
                          </li>
                        ))}
                    </ul>
                  </>
                )}
              </div>
            )}

            {activeTray === 'a11y' && (
              <div className="canvas-tray-body">
                <AccessibilityPanel />
              </div>
            )}
          </aside>
        </>
      )}

      {/* 3. Main Right Area: Top Canvas Header + Course Columns */}
      <div className="canvas-workspace">
        <header className="canvas-top-header">
          <div className="canvas-top-left">
            {course && (
              <button
                type="button"
                className="canvas-hamburger"
                onClick={() => setSubNavOpen((v) => !v)}
                aria-label="Toggle course navigation menu"
                title="Toggle course navigation menu"
              >
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="3" y1="6" x2="21" y2="6" />
                  <line x1="3" y1="12" x2="21" y2="12" />
                  <line x1="3" y1="18" x2="21" y2="18" />
                </svg>
              </button>
            )}
            {activeSection === 'dashboard' ? (
              <h1 className="canvas-dashboard-heading">Dashboard</h1>
            ) : (
              <nav className="canvas-breadcrumbs" aria-label="Breadcrumbs">
                {course ? (
                  <>
                    <a href={`#/c/${course.id}`} className="crumb-course">
                      {codeLabel}
                    </a>
                    {breadcrumb && (
                      <>
                        <span className="crumb-sep" aria-hidden="true">›</span>
                        <span className="crumb-current">{breadcrumb}</span>
                      </>
                    )}
                  </>
                ) : (
                  <span className="crumb-current">{breadcrumb || 'BruinBuddy'}</span>
                )}
              </nav>
            )}
          </div>

          <div className="canvas-top-right">
            {activeSection === 'dashboard' && (
              <button
                type="button"
                className="secondary small hide-narrow"
                onClick={() => {
                  if (resolvedCourseId) navigate(`/c/${resolvedCourseId}`)
                }}
              >
                Today
              </button>
            )}

            {/* Switch Course Dropdown for fast direct switching + test compatibility */}
            {me?.courses?.length > 0 && (
              <select
                className="switcher hide-narrow"
                aria-label="Switch course"
                value={resolvedCourseId || ''}
                onChange={(e) => {
                  const v = e.target.value
                  navigate(v === 'new' ? '/join' : `/c/${v}`)
                }}
              >
                {!resolvedCourseId && <option value="">Choose a course</option>}
                {me.courses.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                    {c.role !== 'student' ? ` · ${ROLE[c.role]}` : ''}
                    {c.status === 'pending' ? ' (unpaid)' : ''}
                  </option>
                ))}
                <option value="new">Join or create a course…</option>
              </select>
            )}

            {/* Immersive Reader button (exact match to Screenshot 3 top-right!) */}
            <button
              type="button"
              className="canvas-immersive-btn"
              onClick={() => openImmersiveReader()}
              title="Open Immersive Reader (Read Aloud, Line Focus, Dyslexia Spacing)"
            >
              <RailIcon name="reader" size={16} />
              <span>Immersive Reader</span>
            </button>

            <button
              type="button"
              className={`canvas-a11y-pill ${activeBadgeCount > 0 ? 'has-active' : ''}`}
              onClick={() => toggleTray('a11y')}
              title="Appearance & Accessibility (Light/Dark, Colorblind, Dyslexia)"
            >
              Appearance{activeBadgeCount > 0 ? ` (${activeBadgeCount})` : ''}
            </button>

            <form className="canvas-search-box hide-narrow" onSubmit={handleHeaderSearch}>
              <input
                type="search"
                placeholder={course ? 'Search this course' : 'Search my courses'}
                aria-label={course ? 'Search this course' : 'Search my courses'}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              <button type="submit" aria-label="Search">
                <RailIcon name="search" size={15} />
              </button>
            </form>
          </div>
        </header>

        <div className="canvas-body-frame">
          {/* 4. Secondary Course Left Navigation Menu (Screenshots 3 & 4) */}
          {course && subNavOpen && (
            <nav className="canvas-course-nav" aria-label="Course Navigation">
              <div className="course-nav-term">2026 Fall Quarter</div>
              <ul className="course-nav-list">
                <li>
                  <a
                    href={`#/c/${course.id}${activeSection === 'preview' ? '/preview' : ''}`}
                    className={activeSection === 'home' ? 'active' : ''}
                    onClick={(e) => {
                      if (onSelectCourseSection) {
                        e.preventDefault()
                        onSelectCourseSection('home')
                      }
                    }}
                  >
                    Home
                  </a>
                </li>
                <li>
                  <a
                    href={`#/c/${course.id}`}
                    className={activeSection === 'syllabus' ? 'active' : ''}
                    onClick={(e) => {
                      if (onSelectCourseSection) {
                        e.preventDefault()
                        onSelectCourseSection('syllabus')
                      }
                    }}
                  >
                    Syllabus & AI Rules
                  </a>
                </li>
                <li>
                  <a
                    href={`#/c/${course.id}`}
                    className={activeSection === 'assignments' ? 'active' : ''}
                    onClick={(e) => {
                      if (onSelectCourseSection) {
                        e.preventDefault()
                        onSelectCourseSection('assignments')
                      }
                    }}
                  >
                    Assignments
                  </a>
                </li>
                <li>
                  <a
                    href={`#/c/${course.id}`}
                    className={activeSection === 'modules' ? 'active' : ''}
                    onClick={(e) => {
                      if (onSelectCourseSection) {
                        e.preventDefault()
                        onSelectCourseSection('modules')
                      }
                    }}
                  >
                    Modules & Files
                  </a>
                </li>
                <li>
                  <button
                    type="button"
                    className={`course-nav-btn ${activeSection === 'chat' ? 'active' : ''}`}
                    onClick={() => openChatOrNew(course, false)}
                  >
                    AI Tutor Notebook
                  </button>
                </li>
                <li>
                  <button
                    type="button"
                    className="course-nav-btn"
                    onClick={() => openChatOrNew(course, true)}
                  >
                    Illustrate Studio
                  </button>
                </li>
              </ul>

              {isStaff && (
                <>
                  <div className="course-nav-divider">Instructor Console</div>
                  <ul className="course-nav-list">
                    {[
                      ['setup', 'Setup'],
                      ['materials', 'Materials'],
                      ['problem-sets', 'Problem Sets'],
                      ['guidelines', 'Guidelines'],
                      ['members', 'People & Codes'],
                      ['dashboard', 'Analytics'],
                      ['pause', 'Pause Tutor'],
                      ['plan', 'Plan & Limits'],
                    ].map(([key, label]) => (
                      <li key={key}>
                        <a
                          href={`#/c/${course.id}/staff/${key}`}
                          className={activeSection === 'staff' && staffTab === key ? 'active' : ''}
                        >
                          {label}
                        </a>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </nav>
          )}

          {/* 5. Center Stage */}
          <main className={`canvas-main-stage ${fullHeight ? 'canvas-stage-chat' : ''}`}>
            {children}
          </main>
        </div>
      </div>
    </div>
  )
}

// Multi-Course Canvas Dashboard matching Screenshot 1 (with course banner thumbnails & mountain/pine-tree line art)
export function CanvasDashboard({ me }) {
  const todayStr = new Date().toLocaleDateString(undefined, { day: 'numeric', month: 'long' })

  return (
    <div className="canvas-dashboard-view">
      <div className="dashboard-date-group">
        <div className="row-between">
          <div>
            <h2 className="dashboard-today-title">Today</h2>
            <div className="muted small">{todayStr}</div>
          </div>
          <button
            type="button"
            className="primary small"
            onClick={() => navigate('/join')}
          >
            + Join or Create Course
          </button>
        </div>

        {me?.courses?.length > 0 ? (
          <div className="dashboard-stream-list">
            {me.courses.map((c) => {
              const code = courseCodeTag(c.name, c.id)
              return (
                <div key={c.id} className="dashboard-stream-row">
                  <a href={`#/c/${c.id}`} className="dashboard-course-thumb">
                    <span className="thumb-top">{code}</span>
                    <span className="thumb-title">{c.name.toUpperCase()}</span>
                    <span className="thumb-campus" aria-hidden="true" />
                  </a>
                  <div className="dashboard-stream-Check">
                    <input type="checkbox" aria-label={`Mark ${c.name} reviewed`} />
                  </div>
                  <div className="dashboard-stream-icon" aria-hidden="true">
                    <RailIcon name="courses" size={18} />
                  </div>
                  <div className="dashboard-stream-main">
                    <div className="dashboard-stream-meta">
                      {code} {c.name.toUpperCase()} · BRUINBUDDY AI TUTOR & ILLUSTRATE STUDIO
                    </div>
                    <a href={`#/c/${c.id}`} className="dashboard-stream-link">
                      Open Course Home, AI Tutor & Concept Animations
                    </a>
                  </div>
                  <div className="dashboard-stream-right">
                    <Badge tone={c.status === 'pending' ? 'warn' : 'good'}>
                      {c.status === 'pending' ? 'Pending' : ROLE[c.role] || 'Student'}
                    </Badge>
                    <div className="muted small">ACTIVE TERM</div>
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <div className="card">
            <h3>No courses enrolled yet</h3>
            <p className="muted">Enter a course code from your instructor or create a course to populate your Bruin Learn Dashboard.</p>
            <button type="button" className="primary" onClick={() => navigate('/join')}>
              Join or create a course
            </button>
          </div>
        )}
      </div>

      {/* Decorative Canvas Mountain, Clouds, Birds & Pine-Tree Line Art Footer (Screenshot 1) */}
      <div className="dashboard-art-footer">
        <div className="muted small dashboard-art-date">Upcoming Study Schedule</div>
        <div className="dashboard-art-stage">
          <svg
            viewBox="0 0 900 220"
            className="dashboard-landscape-svg"
            role="img"
            aria-label="UCLA Bruin Learn study horizon illustration"
          >
            {/* Clouds */}
            <path
              d="M190 70 a22 22 0 0 1 40 -8 a26 26 0 0 1 46 6 a18 18 0 0 1 12 32 H182 a16 16 0 0 1 8 -30 z"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              opacity="0.35"
            />
            {/* Birds */}
            <path d="M520 52 q10 -10 20 0 q10 -10 20 0" fill="none" stroke="currentColor" strokeWidth="2" />
            <path d="M555 38 q8 -8 16 0 q8 -8 16 0" fill="none" stroke="currentColor" strokeWidth="1.8" />
            <path d="M575 68 q9 -9 18 0 q9 -9 18 0" fill="none" stroke="currentColor" strokeWidth="1.8" />
            {/* Mountains on right */}
            <polygon points="620,215 715,75 810,215" fill="var(--bg)" stroke="currentColor" strokeWidth="1.6" opacity="0.55" />
            <polyline points="684,121 715,138 746,121" fill="none" stroke="currentColor" strokeWidth="1.4" opacity="0.45" />
            <polygon points="735,215 805,105 875,215" fill="var(--panel)" stroke="currentColor" strokeWidth="1.6" opacity="0.55" />
            {/* Pine trees left & right */}
            <polygon points="95,215 120,85 145,215" fill="#76c893" stroke="currentColor" strokeWidth="2" />
            <line x1="120" y1="115" x2="120" y2="215" stroke="currentColor" strokeWidth="2" />
            <polygon points="195,215 225,65 255,215" fill="#76c893" stroke="currentColor" strokeWidth="2" />
            <line x1="225" y1="95" x2="225" y2="215" stroke="currentColor" strokeWidth="2" />
            <polygon points="240,215 260,125 280,215" fill="#2774AE" stroke="currentColor" strokeWidth="2" />
            <polygon points="805,215 825,135 845,215" fill="#2774AE" stroke="currentColor" strokeWidth="2" />
            <polygon points="835,215 860,88 885,215" fill="#76c893" stroke="currentColor" strokeWidth="2" />
            <line x1="860" y1="115" x2="860" y2="215" stroke="currentColor" strokeWidth="2" />
          </svg>
          <div className="dashboard-art-caption">Nothing planned yet</div>
        </div>
      </div>
    </div>
  )
}
