import { useEffect, useState } from 'react'
import { useAccessibility } from './accessibility.jsx'
import { api, fileUrl } from './api.js'
import { courseCodeTag } from './CanvasShell.jsx'
import { day, when } from './format.js'
import { navigate } from './router.js'
import { Badge, Banner, ErrorText, Meter, Modal, useAction } from './ui.jsx'

const TOPIC_KINDS = ['lecture_notes', 'reading', 'class_prep', 'other']
const KIND_ORDER = ['lecture_notes', 'reading', 'class_prep', 'problem_set', 'solution', 'other']
const CHAT_KIND = { chat: '', pset: 'Problem set', review: 'Review', quiz: 'Quiz' }

// The chat opens and sends this first message (used by Review, Quiz me and the starter questions).
export const queueFirstMessage = (chatId, text) => {
  try { sessionStorage.setItem(`bb_first_${chatId}`, text) } catch { /* the student can type it */ }
}

export function modeTone(mode) {
  return mode === 'graded' ? 'warn' : mode === 'open' ? 'good' : 'info'
}

export function PauseBanner({ pause }) {
  if (!pause) return null
  if (pause.active) {
    return <Banner kind="warning"><strong>The tutor is paused until {when(pause.until)}.</strong> {pause.message}</Banner>
  }
  if (pause.next) {
    return <p className="muted small">Scheduled pause: {when(pause.next.starts_at)} to {when(pause.next.ends_at)}. {pause.next.message}</p>
  }
  return null
}

export function AllowanceMeter({ allowance }) {
  if (!allowance) return null
  const { percent, period, reached, frees_at: freesAt } = allowance
  return (
    <div className="allowance">
      <div className="allowance-label">
        <span>Tutor allowance this {period}</span>
        <span className="muted">{percent}% used</span>
      </div>
      <Meter percent={percent} label={`Tutor allowance used this ${period}`} />
      {reached && (
        <p className="small error">
          {period === 'term' ? 'You’ve used this term’s allowance.' : `You’ve used this ${period}’s allowance. More frees up ${when(freesAt)}.`}
        </p>
      )}
    </div>
  )
}

export default function CourseHome({ course, preview, reload, section = 'home', onSectionChange }) {
  const [materials, setMaterials] = useState(null)
  const [chats, setChats] = useState([])
  const [picker, setPicker] = useState(null)
  const [filterQuery, setFilterQuery] = useState('')
  const [groupMode, setGroupMode] = useState('type') // 'type' | 'date'
  const [openAccordions, setOpenAccordions] = useState({
    desc: false,
    objectives: true,
    rules: false,
    psetsGroup: true,
    modulesGroup: true,
    chatsGroup: true,
  })
  const [dismissedTodo, setDismissedTodo] = useState([])
  const { busy, error, run } = useAction()
  const { openImmersiveReader } = useAccessibility()

  useEffect(() => {
    api.materials(course.id).then((r) => setMaterials(r.materials)).catch(() => setMaterials([]))
    api.chats(course.id).then(setChats).catch(() => {})
  }, [course.id])

  useEffect(() => { // starter questions are generated in the background after materials change
    if (course.open && !course.starter_questions.length) {
      const t = setTimeout(reload, 4000)
      return () => clearTimeout(t)
    }
    return undefined
  }, [course, reload])

  const toggleAccordion = (key) => {
    setOpenAccordions((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const visible = (materials || []).filter((m) => m.public !== false && (m.status || 'ready') === 'ready')
  const psets = visible.filter((m) => m.kind === 'problem_set')
  const topics = visible.filter((m) => TOPIC_KINDS.includes(m.kind))

  const start = (kind, docId, first, openIllustrate = false) => run(async () => {
    const chat = await api.newChat(course.id, kind, docId)
    if (first) queueFirstMessage(chat.id, first)
    if (openIllustrate) {
      try { sessionStorage.setItem(`bb_open_illustrate_${chat.id}`, '1') } catch { /* ignore */ }
    }
    navigate(`/c/${course.id}/chat/${chat.id}`)
  })

  const entry = (key, title, text, disabled) => (
    <button className="entry" onClick={() => setPicker(key)} disabled={disabled || !course.open}>
      <strong>{title}</strong>
      <span className="muted small">{text}</span>
    </button>
  )

  const codePill = courseCodeTag(course.name, course.id).replace(/^26F-/, '').replace(/-LEC-1$/, '')
  const qLower = filterQuery.trim().toLowerCase()
  const filteredPsets = psets.filter((p) => !qLower || p.title.toLowerCase().includes(qLower))
  const filteredTopics = topics.filter((t) => !qLower || t.title.toLowerCase().includes(qLower))
  const filteredChats = chats.filter((c) => !qLower || c.title.toLowerCase().includes(qLower))

  return (
    <div className="home ucla-course-home">
      {preview && (
        <Banner action={<button className="secondary small" onClick={() => navigate(`/c/${course.id}/staff/setup`)}>Back to staff console</button>}>
          Preview: you’re seeing the course as a student. Your chats are labelled as previews and aren’t counted in the dashboard.
        </Banner>
      )}
      <PauseBanner pause={course.pause} />

      <div className="ucla-course-grid">
        {/* Center Column: UCLA Bruin Learn Hero Banner + Accordions + Assignments/Modules (Screenshots 3 & 4) */}
        <div className="ucla-course-center">
          <div className="home-head">
            <h1 className="ucla-section-heading">
              {section === 'assignments'
                ? 'Assignments & Problem Sets'
                : section === 'modules'
                ? 'Course Modules & Materials'
                : section === 'syllabus'
                ? 'Syllabus & AI Study Guidelines'
                : course.name}
            </h1>
            {section !== 'home' && onSectionChange && (
              <button type="button" className="secondary small" onClick={() => onSectionChange('home')}>
                ← Back to Course Home
              </button>
            )}
          </div>

          {/* UCLA Blue & Gold Hero Card (Screenshot 3) */}
          {section === 'home' && (
            <div className="ucla-hero-card">
              <div className="ucla-hero-banner">
                <div className="ucla-gold-line" aria-hidden="true">
                  <span className="ucla-gold-pill">{codePill}</span>
                </div>
                <h2 className="ucla-hero-title">{course.name.toUpperCase()}</h2>
              </div>

              <div className="ucla-hero-body">
                <h3 className="ucla-gold-heading">Welcome</h3>
                <div className="ucla-welcome-body">
                  <p>
                    Welcome to the <strong>UCLA BruinBuddy AI Study Hub</strong> for <strong>{course.name}</strong>.
                    Every response and visual animation is grounded directly in your instructor’s uploaded lectures, readings,
                    and problem sets with clickable citations.
                  </p>
                </div>

                {/* Collapsible Gray Canvas Accordion Bars (Screenshot 3) */}
                <div className="ucla-accordions">
                  <div className="ucla-accordion-item">
                    <button
                      type="button"
                      className="ucla-accordion-bar"
                      aria-expanded={openAccordions.desc}
                      onClick={() => toggleAccordion('desc')}
                    >
                      <span>Course Description & AI Study Modes</span>
                      <span aria-hidden="true">{openAccordions.desc ? '▲' : '▼'}</span>
                    </button>
                    {openAccordions.desc && (
                      <div className="accordion-panel">
                        <p className="small">
                          Use <strong>AI Tutor Notebook</strong> for Socratic Q&A with page-level source citations, or open the{' '}
                          <strong>✨ Illustrate Studio</strong> to generate interactive Manim 3B1B math animations, Anatomy isometric
                          apparatus diagrams, and step-by-step explainer storyboards that you can watch and download right in the page.
                        </p>
                      </div>
                    )}
                  </div>

                  <div className="ucla-accordion-item">
                    <button
                      type="button"
                      className="ucla-accordion-bar"
                      aria-expanded={openAccordions.objectives}
                      onClick={() => toggleAccordion('objectives')}
                    >
                      <span>Course Objectives & Starter Questions</span>
                      <span aria-hidden="true">{openAccordions.objectives ? '▲' : '▼'}</span>
                    </button>
                    {openAccordions.objectives && (
                      <div className="accordion-panel">
                        {course.starter_questions?.length > 0 ? (
                          <div className="suggest">
                            {course.starter_questions.map((q) => (
                              <button
                                key={q}
                                className="suggestion"
                                disabled={busy || !course.open}
                                onClick={() => start('chat', null, q)}
                              >
                                💬 {q}
                              </button>
                            ))}
                          </div>
                        ) : (
                          <p className="muted small">
                            Ask any conceptual question, request a custom study plan, or generate a visual animation for a lecture topic.
                          </p>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="ucla-accordion-item">
                    <button
                      type="button"
                      className="ucla-accordion-bar"
                      aria-expanded={openAccordions.rules}
                      onClick={() => toggleAccordion('rules')}
                    >
                      <span>Academic Integrity & Problem Set Guardrails</span>
                      <span aria-hidden="true">{openAccordions.rules ? '▲' : '▼'}</span>
                    </button>
                    {openAccordions.rules && (
                      <div className="accordion-panel">
                        <p className="small">
                          On <strong>Graded</strong> problem sets, BruinBuddy acts as a Socratic teaching assistant: it checks your reasoning,
                          explains underlying concepts, and points you to relevant lecture passages without handing over final answers.
                        </p>
                      </div>
                    )}
                  </div>
                </div>

                {/* Modules Section with UCLA Gold Underline + Getting Started Bar + Module Pills (Screenshot 3) */}
                <h3 className="ucla-gold-heading">Modules</h3>
                {!course.open ? (
                  <div className="empty card">
                    <h2>The tutor isn’t open yet</h2>
                    <p className="muted">
                      {preview
                        ? 'Upload at least one lecture, reading or problem set (Materials tab) to open the tutor.'
                        : 'Your instructor hasn’t added course materials yet. Check back soon.'}
                    </p>
                  </div>
                ) : (
                  <div className="ucla-modules-showcase">
                    <button
                      type="button"
                      className="ucla-getting-started-bar"
                      disabled={busy}
                      onClick={() => start('chat', null)}
                    >
                      Getting Started — Start a New AI Tutor Chat
                    </button>
                    <div className="ucla-module-pills">
                      <button
                        type="button"
                        className="ucla-module-pill"
                        disabled={materials !== null && !psets.length}
                        onClick={() => setPicker('pset')}
                      >
                        Module 1: Problem Sets
                      </button>
                      <button
                        type="button"
                        className="ucla-module-pill"
                        disabled={materials !== null && !topics.length}
                        onClick={() => setPicker('review')}
                      >
                        Module 2: Review Topic
                      </button>
                      <button
                        type="button"
                        className="ucla-module-pill"
                        onClick={() => setPicker('quiz')}
                      >
                        Module 3: Quiz Me
                      </button>
                      <button
                        type="button"
                        className="ucla-module-pill"
                        disabled={busy}
                        onClick={() => start('chat', null, null, true)}
                      >
                        Module 4: ✨ Illustrate
                      </button>
                      <button
                        type="button"
                        className="ucla-module-pill"
                        onClick={() => setPicker('browse')}
                      >
                        Module 5: Course Files
                      </button>
                    </div>

                    {/* Preserve exact button labels for existing tests & quick actions */}
                    <div className="entries">
                      {entry('pset', 'Help with a problem set', 'Hints and guidance on an assigned set', materials !== null && !psets.length)}
                      {entry('review', 'Review a topic', 'A study plan for one lecture or reading', materials !== null && !topics.length)}
                      {entry('quiz', 'Quiz me', 'Practice questions, one at a time')}
                      {entry('browse', 'Browse materials', 'Open the course documents')}
                    </div>
                    <ErrorText error={error} />
                    <div className="inline wrap">
                      <button className="primary" disabled={busy} onClick={() => start('chat', null)}>
                        Start a new chat
                      </button>
                      <button
                        type="button"
                        className="secondary"
                        disabled={busy}
                        onClick={() => start('chat', null, null, true)}
                      >
                        ✨ Open Illustrate Studio
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Structured Canvas Search + SHOW BY DATE / SHOW BY TYPE Accordion Groups (Screenshot 4) */}
          <div className="canvas-assignments-block">
            <div className="canvas-filter-toolbar">
              <div className="canvas-filter-search">
                <input
                  type="search"
                  placeholder="🔍 Search assignments, materials, or chats..."
                  aria-label="Search assignments, materials, or chats"
                  value={filterQuery}
                  onChange={(e) => setFilterQuery(e.target.value)}
                />
              </div>
              <div className="canvas-filter-toggles">
                <button
                  type="button"
                  className={`canvas-show-btn ${groupMode === 'date' ? 'active' : ''}`}
                  onClick={() => setGroupMode('date')}
                >
                  SHOW BY DATE
                </button>
                <button
                  type="button"
                  className={`canvas-show-btn ${groupMode === 'type' ? 'active' : ''}`}
                  onClick={() => setGroupMode('type')}
                >
                  SHOW BY TYPE
                </button>
              </div>
            </div>

            {/* Group 1: Problem Sets / Assignments */}
            {(section === 'home' || section === 'assignments' || section === 'syllabus') && (
              <div className="canvas-group-box">
                <button
                  type="button"
                  className="canvas-group-header"
                  onClick={() => toggleAccordion('psetsGroup')}
                >
                  <span>{openAccordions.psetsGroup ? '▾' : '▸'} Problem Sets & Assignments</span>
                  <span className="muted small">{filteredPsets.length} item(s)</span>
                </button>
                {openAccordions.psetsGroup && (
                  <div className="canvas-group-rows">
                    {filteredPsets.length > 0 ? (
                      filteredPsets.map((p) => (
                        <div key={p.id} className="canvas-item-row">
                          <span className="canvas-item-icon" aria-hidden="true">📝</span>
                          <div className="canvas-item-main">
                            <button
                              type="button"
                              className="canvas-row-title-btn"
                              disabled={busy || !course.open}
                              onClick={() => start('pset', p.id)}
                            >
                              {p.title}
                            </button>
                            <div className="muted small">
                              Rule: {p.mode_label || 'Guided Help'} {p.due_at ? `| Due ${when(p.due_at)}` : '| Active Term'}
                            </div>
                          </div>
                          <div className="canvas-item-actions">
                            <Badge tone={modeTone(p.effective_mode || p.mode)}>{p.mode_label}</Badge>
                            <a
                              className="secondary small btnlink"
                              href={fileUrl(p.url)}
                              target="_blank"
                              rel="noreferrer"
                            >
                              PDF
                            </a>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="canvas-item-empty muted small">
                        No problem sets uploaded yet.
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Group 2: Lecture Notes & Readings */}
            {(section === 'home' || section === 'modules') && (
              <div className="canvas-group-box">
                <button
                  type="button"
                  className="canvas-group-header"
                  onClick={() => toggleAccordion('modulesGroup')}
                >
                  <span>{openAccordions.modulesGroup ? '▾' : '▸'} Course Modules, Lecture Notes & Readings</span>
                  <span className="muted small">{filteredTopics.length} item(s)</span>
                </button>
                {openAccordions.modulesGroup && (
                  <div className="canvas-group-rows">
                    {filteredTopics.length > 0 ? (
                      filteredTopics.map((t) => (
                        <div key={t.id} className="canvas-item-row">
                          <span className="canvas-item-icon" aria-hidden="true">📄</span>
                          <div className="canvas-item-main">
                            <button
                              type="button"
                              className="canvas-row-title-btn"
                              disabled={busy || !course.open}
                              onClick={() => start('review', t.id, `Help me review ${t.title}.`)}
                            >
                              {t.title}
                            </button>
                            <div className="muted small">
                              {t.kind_label} · Click to launch AI Review or Illustrate
                            </div>
                          </div>
                          <div className="canvas-item-actions">
                            <button
                              type="button"
                              className="secondary small"
                              disabled={busy || !course.open}
                              onClick={() => start('review', t.id, `Illustrate the main concept of ${t.title}.`, true)}
                            >
                              ✨ Illustrate
                            </button>
                            <a
                              className="secondary small btnlink"
                              href={fileUrl(t.url)}
                              target="_blank"
                              rel="noreferrer"
                            >
                              Open
                            </a>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="canvas-item-empty muted small">
                        No lecture notes or readings matched.
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Group 3: Recent AI Tutor Chats */}
            {chats.length > 0 && (
              <div className="canvas-group-box">
                <button
                  type="button"
                  className="canvas-group-header"
                  onClick={() => toggleAccordion('chatsGroup')}
                >
                  <span>{openAccordions.chatsGroup ? '▾' : '▸'} Your Chats & Saved Illustrations</span>
                  <span className="muted small">{filteredChats.length} thread(s)</span>
                </button>
                {openAccordions.chatsGroup && (
                  <ul className="chatlinks canvas-group-rows">
                    {(groupMode === 'date' ? filteredChats : [...filteredChats].sort((a, b) => (a.kind || '').localeCompare(b.kind || '')))
                      .slice(0, 12)
                      .map((c) => (
                        <li key={c.id} className="canvas-item-row">
                          <span className="canvas-item-icon" aria-hidden="true">💬</span>
                          <a href={`#/c/${course.id}/chat/${c.id}`} className="canvas-chat-link">
                            {c.title}
                          </a>
                          {CHAT_KIND[c.kind] && <Badge>{CHAT_KIND[c.kind]}</Badge>}
                          <span className="muted small">{day(c.updated_at)}</span>
                        </li>
                      ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right Sidebar Column: Course Action Buttons + Allowance + To Do List (Screenshot 3) */}
        <aside className="ucla-course-right" aria-label="Course Stream and To Do">
          <div className="ucla-side-actions">
            <button
              type="button"
              className="ucla-side-action-btn"
              disabled={busy || !course.open}
              onClick={() => start('chat', null)}
            >
              📊 Start AI Tutor Session
            </button>
            <button
              type="button"
              className="ucla-side-action-btn"
              disabled={busy || !course.open}
              onClick={() => start('chat', null, null, true)}
            >
              ✨ Open Illustrate Studio
            </button>
            <button
              type="button"
              className="ucla-side-action-btn"
              onClick={() => openImmersiveReader()}
            >
              📖 Open Immersive Reader
            </button>
          </div>

          <div className="ucla-allowance-card">
            <AllowanceMeter allowance={course.allowance} />
          </div>

          <div className="ucla-todo-section">
            <h3 className="ucla-todo-heading">To do</h3>
            <hr className="canvas-tray-hr" />
            {visible.filter((m) => !dismissedTodo.includes(m.id)).length > 0 ? (
              <ul className="ucla-todo-list">
                {visible
                  .filter((m) => !dismissedTodo.includes(m.id))
                  .slice(0, 6)
                  .map((m) => (
                    <li key={m.id} className="ucla-todo-item">
                      <span className="todo-icon" aria-hidden="true">
                        {m.kind === 'problem_set' ? '📝' : '📄'}
                      </span>
                      <div className="todo-body">
                        <button
                          type="button"
                          className="todo-link"
                          disabled={busy || !course.open}
                          onClick={() =>
                            m.kind === 'problem_set'
                              ? start('pset', m.id)
                              : start('review', m.id, `Help me review ${m.title}.`)
                          }
                        >
                          {m.title}
                        </button>
                        <div className="muted small">
                          {course.name}
                          <br />
                          {m.kind === 'problem_set' ? m.mode_label || 'Problem Set' : m.kind_label}
                        </div>
                      </div>
                      <button
                        type="button"
                        className="todo-dismiss"
                        aria-label={`Dismiss ${m.title}`}
                        onClick={() => setDismissedTodo((prev) => [...prev, m.id])}
                      >
                        ✕
                      </button>
                    </li>
                  ))}
              </ul>
            ) : (
              <p className="muted small">Nothing queued right now—start a chat or review a topic!</p>
            )}
          </div>
        </aside>
      </div>

      {picker === 'pset' && (
        <Modal title="Help with a problem set" onClose={() => setPicker(null)}>
          <p className="muted small">The set’s rule applies in the chat, even if you reword the problem.</p>
          <ul className="picklist">
            {psets.map((p) => (
              <li key={p.id}>
                <button className="pick" disabled={busy} onClick={() => start('pset', p.id)}>
                  <span>{p.title}</span><Badge tone={modeTone(p.effective_mode || p.mode)}>{p.mode_label}</Badge>
                </button>
              </li>
            ))}
          </ul>
        </Modal>
      )}
      {picker === 'review' && (
        <Modal title="Review a topic" onClose={() => setPicker(null)}>
          <ul className="picklist">
            {topics.map((t) => (
              <li key={t.id}>
                <button className="pick" disabled={busy} onClick={() => start('review', t.id, `Help me review ${t.title}.`)}>
                  <span>{t.title}</span><span className="muted small">{t.kind_label}</span>
                </button>
              </li>
            ))}
          </ul>
        </Modal>
      )}
      {picker === 'quiz' && (
        <Modal title="Quiz me" onClose={() => setPicker(null)}>
          <ul className="picklist">
            <li>
              <button className="pick" disabled={busy} onClick={() => start('quiz', null, 'Quiz me on the course so far.')}>
                <span><strong>Anything from the course</strong></span>
              </button>
            </li>
            {topics.map((t) => (
              <li key={t.id}>
                <button className="pick" disabled={busy} onClick={() => start('quiz', t.id, `Quiz me on ${t.title}.`)}>
                  <span>{t.title}</span><span className="muted small">{t.kind_label}</span>
                </button>
              </li>
            ))}
          </ul>
        </Modal>
      )}
      {picker === 'browse' && (
        <Modal title="Course materials" onClose={() => setPicker(null)}>
          {KIND_ORDER.map((k) => {
            const items = visible.filter((m) => m.kind === k)
            if (!items.length) return null
            return (
              <section key={k}>
                <h3 className="section-title">{items[0].kind_label}</h3>
                <ul className="picklist">
                  {items.map((m) => (
                    <li key={m.id}>
                      <a className="pick" href={fileUrl(m.url)} target="_blank" rel="noreferrer">
                        <span>{m.title}</span>
                        {m.kind === 'problem_set' && <Badge tone={modeTone(m.effective_mode || m.mode)}>{m.mode_label}</Badge>}
                      </a>
                    </li>
                  ))}
                </ul>
              </section>
            )
          })}
        </Modal>
      )}
    </div>
  )
}
