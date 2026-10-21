import { useEffect, useState } from 'react'
import { api, fileUrl } from './api.js'
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

export default function CourseHome({ course, preview, reload }) {
  const [materials, setMaterials] = useState(null)
  const [chats, setChats] = useState([])
  const [picker, setPicker] = useState(null)
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

  const start = (kind, docId, first) => run(async () => {
    const chat = await api.newChat(course.id, kind, docId)
    if (first) queueFirstMessage(chat.id, first)
    navigate(`/c/${course.id}/chat/${chat.id}`)
  })

  const entry = (key, title, text, disabled) => (
    <button className="entry" onClick={() => setPicker(key)} disabled={disabled || !course.open}>
      <strong>{title}</strong>
      <span className="muted small">{text}</span>
    </button>
  )

  return (
    <div className="home">
      {preview && (
        <Banner action={<button className="secondary small" onClick={() => navigate(`/c/${course.id}/staff/setup`)}>Back to staff console</button>}>
          Preview: you’re seeing the course as a student. Your chats are labelled as previews and aren’t counted in the dashboard.
        </Banner>
      )}
      <PauseBanner pause={course.pause} />
      <div className="home-head">
        <h1>{course.name}</h1>
        <AllowanceMeter allowance={course.allowance} />
      </div>

      {!course.open ? (
        <div className="empty card">
          <h2>The tutor isn’t open yet</h2>
          <p className="muted">
            {preview ? 'Upload at least one lecture, reading or problem set (Materials tab) to open the tutor.'
              : 'Your instructor hasn’t added course materials yet. Check back soon.'}
          </p>
        </div>
      ) : (
        <>
          <div className="entries">
            {entry('pset', 'Help with a problem set', 'Hints and guidance on an assigned set', materials !== null && !psets.length)}
            {entry('review', 'Review a topic', 'A study plan for one lecture or reading', materials !== null && !topics.length)}
            {entry('quiz', 'Quiz me', 'Practice questions, one at a time')}
            {entry('browse', 'Browse materials', 'Open the course documents')}
          </div>
          <ErrorText error={error} />

          {course.starter_questions.length > 0 && (
            <section>
              <h2 className="section-title">Try asking</h2>
              <div className="suggest">
                {course.starter_questions.map((q) => (
                  <button key={q} className="suggestion" disabled={busy} onClick={() => start('chat', null, q)}>{q}</button>
                ))}
              </div>
            </section>
          )}
          <p><button className="primary" disabled={busy} onClick={() => start('chat', null)}>Start a new chat</button></p>
        </>
      )}

      {chats.length > 0 && (
        <section>
          <h2 className="section-title">Your chats</h2>
          <ul className="chatlinks">
            {chats.slice(0, 12).map((c) => (
              <li key={c.id}>
                <a href={`#/c/${course.id}/chat/${c.id}`}>{c.title}</a>
                {CHAT_KIND[c.kind] && <Badge>{CHAT_KIND[c.kind]}</Badge>}
                <span className="muted small">{day(c.updated_at)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

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
