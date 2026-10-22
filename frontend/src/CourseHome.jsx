import { useEffect, useState } from 'react'
import { api, fileUrl } from './api.js'
import { courseCodeTag, RailIcon } from './CanvasShell.jsx'
import { AssignmentList } from './GuidedAssignments.jsx'
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
  const { busy, error, run } = useAction()

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
  const filteredVisible = visible.filter((m) => !qLower || m.title.toLowerCase().includes(qLower))

  return (
    <div className="home ucla-course-home">
      {preview && (
        <Banner action={<button className="secondary small" onClick={() => navigate(`/c/${course.id}/staff/setup`)}>Back to staff console</button>}>
          Preview: you’re seeing the course as a student. Your chats are labelled as previews and aren’t counted in the dashboard.
        </Banner>
      )}
      <PauseBanner pause={course.pause} />

      <div className="ucla-course-grid">
        <div className="ucla-course-center">
          <div className="home-head">
            <h1 className="ucla-section-heading">
              {section === 'psets'
                ? 'Problem Sets'
                : section === 'materials'
                ? 'Course Materials'
                : course.name}
            </h1>
            {section !== 'home' && onSectionChange && (
              <button type="button" className="secondary small" onClick={() => onSectionChange('home')}>
                ← Back to Course Home
              </button>
            )}
          </div>

          {/* 1. HOME VIEW: UCLA Blue & Gold Hero Card + 4 Real Study Modes + Starter Questions + Chats */}
          {section === 'home' && (
            <>
              <div className="ucla-hero-card">
                <div className="ucla-hero-banner">
                  <div className="ucla-gold-line" aria-hidden="true">
                    <span className="ucla-gold-pill">{codePill}</span>
                  </div>
                  <h2 className="ucla-hero-title">{course.name.toUpperCase()}</h2>
                </div>

                <div className="ucla-hero-body">
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
                    <>
                      <h3 className="ucla-gold-heading">Study Tools</h3>
                      <div className="entries">
                        {entry('pset', 'Help with a problem set', 'Hints and guidance on an assigned set', materials !== null && !psets.length)}
                        {entry('review', 'Review a topic', 'A study plan for one lecture or reading', materials !== null && !topics.length)}
                        {entry('quiz', 'Quiz me', 'Practice questions, one at a time')}
                        {entry('browse', 'Browse materials', 'Open the course documents')}
                      </div>
                      <ErrorText error={error} />

                      <div className="inline wrap" style={{ marginTop: 8 }}>
                        <button className="primary" disabled={busy} onClick={() => start('chat', null)}>
                          Start a new chat
                        </button>
                        <button
                          type="button"
                          className="secondary"
                          disabled={busy}
                          onClick={() => start('chat', null, null, true)}
                        >
                          Open Illustrate Studio
                        </button>
                      </div>

                      {course.starter_questions.length > 0 && (
                        <section style={{ marginTop: 20 }}>
                          <h3 className="ucla-gold-heading">Try asking</h3>
                          <div className="suggest">
                            {course.starter_questions.map((q) => (
                              <button key={q} className="suggestion" disabled={busy} onClick={() => start('chat', null, q)}>
                                {q}
                              </button>
                            ))}
                          </div>
                        </section>
                      )}
                    </>
                  )}
                </div>
              </div>

              {chats.length > 0 && (
                <div className="canvas-group-box">
                  <div className="canvas-group-header">
                    <span>Your chats</span>
                    <span className="muted small">{chats.length}</span>
                  </div>
                  <ul className="chatlinks canvas-group-rows">
                    {chats.slice(0, 12).map((c) => (
                      <li key={c.id} className="canvas-item-row">
                        <span className="canvas-item-icon" aria-hidden="true">
                          <RailIcon name="chat" size={18} />
                        </span>
                        <a href={`#/c/${course.id}/chat/${c.id}`} className="canvas-chat-link">
                          {c.title}
                        </a>
                        {CHAT_KIND[c.kind] && <Badge>{CHAT_KIND[c.kind]}</Badge>}
                        <span className="muted small">{day(c.updated_at)}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}

          {/* 2. PROBLEM SETS VIEW: Strictly backed by uploaded problem_set documents */}
          {section === 'psets' && (
            <div className="canvas-assignments-block">
              <div className="canvas-filter-toolbar">
                <div className="canvas-filter-search">
                  <input
                    type="search"
                    placeholder="Filter problem sets..."
                    aria-label="Filter problem sets"
                    value={filterQuery}
                    onChange={(e) => setFilterQuery(e.target.value)}
                  />
                </div>
              </div>

              <div className="canvas-group-box">
                <div className="canvas-group-header">
                  <span>Problem Sets</span>
                  <span className="muted small">{filteredPsets.length} set(s)</span>
                </div>
                <div className="canvas-group-rows">
                  {filteredPsets.length > 0 ? (
                    filteredPsets.map((p) => (
                      <div key={p.id} className="canvas-item-row">
                        <span className="canvas-item-icon" aria-hidden="true">
                          <RailIcon name="assignment" size={18} />
                        </span>
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
                            {p.mode_label} {p.release_at ? `· Solutions release ${when(p.release_at)}` : ''}
                          </div>
                        </div>
                        <div className="canvas-item-actions">
                          <Badge tone={modeTone(p.effective_mode || p.mode)}>{p.mode_label}</Badge>
                          <button
                            type="button"
                            className="primary small"
                            disabled={busy || !course.open}
                            onClick={() => start('pset', p.id)}
                          >
                            Ask Tutor
                          </button>
                          <a
                            className="secondary small btnlink"
                            href={fileUrl(p.url)}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Open file
                          </a>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="canvas-item-empty muted small">
                      No problem sets have been uploaded to this course yet.
                    </div>
                  )}
                </div>
              </div>
              <AssignmentList course={course} compact />
            </div>
          )}

          {/* 3. MATERIALS VIEW: Strictly backed by uploaded course documents */}
          {section === 'materials' && (
            <div className="canvas-assignments-block">
              <div className="canvas-filter-toolbar">
                <div className="canvas-filter-search">
                  <input
                    type="search"
                    placeholder="Filter course materials..."
                    aria-label="Filter course materials"
                    value={filterQuery}
                    onChange={(e) => setFilterQuery(e.target.value)}
                  />
                </div>
              </div>

              {filteredVisible.length === 0 ? (
                <div className="card muted small">No course materials found.</div>
              ) : (
                KIND_ORDER.map((k) => {
                  const items = filteredVisible.filter((m) => m.kind === k)
                  if (!items.length) return null
                  return (
                    <div key={k} className="canvas-group-box">
                      <div className="canvas-group-header">
                        <span>{items[0].kind_label}</span>
                        <span className="muted small">{items.length} file(s)</span>
                      </div>
                      <div className="canvas-group-rows">
                        {items.map((m) => (
                          <div key={m.id} className="canvas-item-row">
                            <span className="canvas-item-icon" aria-hidden="true">
                              <RailIcon name={m.kind === 'problem_set' ? 'assignment' : 'doc'} size={18} />
                            </span>
                            <div className="canvas-item-main">
                              <a
                                className="canvas-chat-link"
                                href={fileUrl(m.url)}
                                target="_blank"
                                rel="noreferrer"
                              >
                                {m.title}
                              </a>
                              <div className="muted small">
                                {m.kind_label}{m.pages ? ` · ${m.pages} pages` : ''}
                              </div>
                            </div>
                            <div className="canvas-item-actions">
                              {m.kind === 'problem_set' ? (
                                <>
                                  <Badge tone={modeTone(m.effective_mode || m.mode)}>{m.mode_label}</Badge>
                                  <button
                                    type="button"
                                    className="secondary small"
                                    disabled={busy || !course.open}
                                    onClick={() => start('pset', m.id)}
                                  >
                                    Help with set
                                  </button>
                                </>
                              ) : TOPIC_KINDS.includes(m.kind) ? (
                                <>
                                  <button
                                    type="button"
                                    className="secondary small"
                                    disabled={busy || !course.open}
                                    onClick={() => start('review', m.id, `Help me review ${m.title}.`)}
                                  >
                                    Review
                                  </button>
                                  <button
                                    type="button"
                                    className="secondary small"
                                    disabled={busy || !course.open}
                                    onClick={() => start('quiz', m.id, `Quiz me on ${m.title}.`)}
                                  >
                                    Quiz me
                                  </button>
                                </>
                              ) : null}
                              <a
                                className="secondary small btnlink"
                                href={fileUrl(m.url)}
                                target="_blank"
                                rel="noreferrer"
                              >
                                Open
                              </a>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          )}
        </div>

        {/* Right Sidebar: Allowance Meter + Real Uploaded Course Documents */}
        <aside className="ucla-course-right" aria-label="Course Allowance and Materials">
          <div className="ucla-allowance-card">
            <AllowanceMeter allowance={course.allowance} />
          </div>

          <div className="ucla-todo-section">
            <h3 className="ucla-todo-heading">Course Materials</h3>
            <hr className="canvas-tray-hr" />
            {visible.length > 0 ? (
              <ul className="ucla-todo-list">
                {visible.slice(0, 8).map((m) => (
                  <li key={m.id} className="ucla-todo-item">
                    <span className="todo-icon" aria-hidden="true">
                      <RailIcon name={m.kind === 'problem_set' ? 'assignment' : 'doc'} size={16} />
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
                        {m.kind === 'problem_set' ? m.mode_label : m.kind_label}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted small">No materials uploaded yet.</p>
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
