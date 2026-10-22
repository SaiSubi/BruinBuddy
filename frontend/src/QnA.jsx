import { useEffect, useRef, useState } from 'react'
import { api, fileUrl } from './api.js'
import { RailIcon } from './CanvasShell.jsx'
import { day, when } from './format.js'
import { Markdown } from './Message.jsx'
import { navigate } from './router.js'
import { Badge, Banner, ErrorText, Loading, Modal, useAction } from './ui.jsx'

// Students' Q&A with the AI teaching assistant. A student only ever loads their own threads and the published FAQ.

export const QNA_STATUS = {
  open: ['Waiting', 'neutral'], ai_answered: ['Answered by AI', 'info'], escalated: ['With course staff', 'warn'],
  staff_answered: ['Staff replied', 'good'], resolved: ['Resolved', 'good'],
}

export function QnaStatus({ status }) {
  const [label, tone] = QNA_STATUS[status] || QNA_STATUS.open
  return <Badge tone={tone}>{label}</Badge>
}

function Sources({ citations }) {
  if (!citations?.length) return null
  return (
    <details className="qna-sources">
      <summary>Sources ({citations.length})</summary>
      <ol>
        {citations.map((c) => (
          <li key={c.n} id={`qna-src-${c.n}`}>
            {c.kind === 'qa' ? (
              <><strong>Past Q&amp;A</strong><pre className="srctext">{c.text}</pre></>
            ) : (
              <>
                <strong>{c.title}</strong>, p. {c.page}{' '}
                {c.url && <a href={fileUrl(c.url)} target="_blank" rel="noreferrer">Open document</a>}
                <pre className="srctext">{c.text}</pre>
              </>
            )}
          </li>
        ))}
      </ol>
    </details>
  )
}

export function QnaMessage({ m, studentLabel = 'You' }) {
  if (m.role === 'system') return <p className="qna-system muted small" role="status">{m.content}</p>
  const who = m.role === 'student' ? studentLabel : m.role === 'staff' ? `${m.author_name || 'Course staff'} · Course staff` : 'BruinBuddy TA'
  return (
    <div className={`msg ${m.role === 'student' ? 'user' : 'tutor'} qna-${m.role}`}>
      <div className="who">
        {who} {m.role === 'ai' && <span className="tag">AI-generated</span>}
        <span className="muted small"> · {when(m.created_at)}</span>
      </div>
      <div className="bubble">
        {m.role === 'student' ? m.content : (
          <Markdown text={m.content} citations={m.citations || []}
                    onCite={(c) => document.getElementById(`qna-src-${c.n}`)?.closest('details')?.setAttribute('open', '')} />
        )}
      </div>
      {m.role === 'ai' && <Sources citations={m.citations} />}
    </div>
  )
}

function Thread({ course, threadId }) {
  const [t, setT] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [input, setInput] = useState('')
  const [escalating, setEscalating] = useState(false)
  const [note, setNote] = useState('')
  const { busy, error, run } = useAction()
  const bottom = useRef(null)
  useEffect(() => { api.qnaThread(threadId).then(setT).catch(setLoadError) }, [threadId])
  useEffect(() => { bottom.current?.scrollIntoView({ block: 'end' }) }, [t?.messages?.length])

  if (loadError) {
    return (
      <div className="narrow">
        <Banner kind="error">{loadError.status === 404 ? 'This question doesn’t exist or isn’t yours.' : loadError.message}</Banner>
        <a className="secondary btnlink" href={`#/c/${course.id}/qna`}>Back to Q&amp;A</a>
      </div>
    )
  }
  if (!t) return <Loading />
  const send = () => run(async () => { setT(await api.qnaFollowUp(t.id, input.trim())); setInput('') })
  const escalate = () => run(async () => { setT(await api.qnaEscalate(t.id, note.trim())); setEscalating(false); setNote('') })
  const resolve = () => run(async () => setT(await api.qnaResolve(t.id)))

  return (
    <div className="qna-thread narrow-wide">
      <a className="link small" href={`#/c/${course.id}/qna`}>← All questions</a>
      <div className="row-between">
        <h1 className="ga-title">{t.title}</h1>
        <QnaStatus status={t.status} />
      </div>
      <p className="muted small">{t.category_label}{t.escalated ? ' · Your course staff can see this question.' : ' · Only you can see this question unless you send it to the course staff.'}</p>
      <div className="card qna-log" role="log" aria-live="polite" aria-label="Conversation">
        {t.messages.map((m) => <QnaMessage key={m.id} m={m} />)}
        {busy && <p className="muted small" aria-hidden="true">Working on it…</p>}
        <div ref={bottom} />
      </div>
      <ErrorText error={error} />
      {!t.escalated && t.status !== 'resolved' && (
        <div className="inline wrap qna-actions">
          {t.status === 'ai_answered' && <button className="secondary" disabled={busy} onClick={resolve}>This answered my question</button>}
          <button className="primary" disabled={busy} onClick={() => setEscalating(true)}>
            {t.status === 'ai_answered' ? 'Not satisfied? Ask the course staff' : 'Send to the course staff'}
          </button>
        </div>
      )}
      {t.escalated && t.status === 'staff_answered' && (
        <div className="inline wrap qna-actions">
          <button className="secondary" disabled={busy} onClick={resolve}>Mark as resolved</button>
        </div>
      )}
      <form className="composer qna-composer" onSubmit={(e) => { e.preventDefault(); if (input.trim()) send() }}>
        <textarea aria-label="Follow-up" rows={2} maxLength={4000} value={input} onChange={(e) => setInput(e.target.value)}
                  placeholder={t.escalated ? 'Add a follow-up for the course staff…' : 'Ask a follow-up…'} />
        <button className="primary" type="submit" disabled={busy || !input.trim()}>Send</button>
      </form>
      {escalating && (
        <Modal title="Ask the course staff" onClose={() => setEscalating(false)}>
          <p>Your question and this conversation will go to the course staff (your professor and TAs). They’ll reply here.</p>
          <label htmlFor="qna-note" className="block">Anything to add? <span className="muted small">(optional)</span></label>
          <textarea id="qna-note" rows={3} maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)}
                    placeholder="For example, what was missing from the answer" style={{ width: '100%' }} />
          <div className="inline" style={{ marginTop: 10 }}>
            <button className="primary" disabled={busy} onClick={escalate}>Send to staff</button>
            <button className="secondary" onClick={() => setEscalating(false)}>Cancel</button>
          </div>
        </Modal>
      )}
    </div>
  )
}

function Home({ course, preview }) {
  const [data, setData] = useState(null)
  const [question, setQuestion] = useState('')
  const { busy, error, run } = useAction()
  useEffect(() => { api.qna(course.id).then(setData).catch(() => setData({ threads: [], faq: [], staff_topics: [] })) }, [course.id])
  if (!data) return <Loading />
  const ask = () => run(async () => {
    const t = await api.askQna(course.id, question.trim())
    navigate(`/c/${course.id}/qna/${t.id}`)
  })
  return (
    <div className="qna-home narrow-wide">
      {preview && (
        <Banner action={<button className="secondary small" onClick={() => navigate(`/c/${course.id}/staff/qna`)}>Open staff inbox</button>}>
          Preview: this is the student view. Questions you ask here are labelled as previews.
        </Banner>
      )}
      <h1 className="ucla-section-heading">Ask the course</h1>
      <p className="muted">
        Questions about the course, the assignments or logistics. BruinBuddy’s AI teaching assistant answers from what
        your course staff have answered before and the course materials. If the answer doesn’t help, send it to the
        course staff with one click.
      </p>
      {data.assistant_enabled === false ? (
        <Banner>The AI assistant is off for this course: your questions go straight to the course staff.</Banner>
      ) : data.staff_topics.length > 0 && (
        <p className="small muted">Always answered by the course staff, not the AI: {data.staff_topics.join('; ')}.</p>
      )}
      <form className="card qna-ask" onSubmit={(e) => { e.preventDefault(); if (question.trim().length >= 3) ask() }}>
        <label htmlFor="qna-question"><strong>Your question</strong></label>
        <textarea id="qna-question" rows={3} maxLength={4000} value={question} onChange={(e) => setQuestion(e.target.value)}
                  placeholder="For example: Can we use Python instead of R for the simulations?" />
        <ErrorText error={error} />
        <div className="inline"><button className="primary" type="submit" disabled={busy || question.trim().length < 3}>
          {busy ? 'Asking…' : 'Ask'}
        </button></div>
      </form>

      {data.faq.length > 0 && (
        <section>
          <h2 className="ucla-gold-heading">Frequently asked</h2>
          {data.faq.map((f) => (
            <details key={f.id} className="qna-faq card">
              <summary>{f.question}</summary>
              <Markdown text={f.answer} />
            </details>
          ))}
        </section>
      )}

      <div className="canvas-group-box">
        <div className="canvas-group-header"><span>Your questions</span><span className="muted small">{data.threads.length}</span></div>
        <div className="canvas-group-rows">
          {data.threads.length ? data.threads.map((t) => (
            <div key={t.id} className="canvas-item-row">
              <span className="canvas-item-icon" aria-hidden="true"><RailIcon name="help" size={18} /></span>
              <div className="canvas-item-main">
                <a className="canvas-chat-link" href={`#/c/${course.id}/qna/${t.id}`}>{t.title}</a>
                <div className="muted small">{t.category_label} · {day(t.updated_at)}</div>
              </div>
              <div className="canvas-item-actions"><QnaStatus status={t.status} /></div>
            </div>
          )) : <div className="canvas-item-empty muted small">You haven’t asked anything yet.</div>}
        </div>
      </div>
    </div>
  )
}

export default function QnA({ course, threadId, preview }) {
  return threadId ? <Thread key={threadId} course={course} threadId={threadId} /> : <Home course={course} preview={preview} />
}
