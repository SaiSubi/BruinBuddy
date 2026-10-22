import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import { day, when } from '../format.js'
import { Markdown } from '../Message.jsx'
import { QnaMessage, QnaStatus } from '../QnA.jsx'
import { Badge, Banner, ErrorText, Loading, useAction } from '../ui.jsx'

// The AI teaching assistant, staff side: the shared inbox of escalated questions, the Q&A knowledge base, and rules.

function SaveToKnowledge({ thread, onSaved }) {
  const firstQ = thread.messages.find((m) => m.role === 'student')?.content || thread.title
  const lastA = [...thread.messages].reverse().find((m) => m.role === 'staff')?.content || ''
  const [q, setQ] = useState(firstQ)
  const [a, setA] = useState(lastA)
  const [faq, setFaq] = useState(false)
  const { busy, error, run } = useAction()
  return (
    <div className="card qna-save">
      <h3>Save to the knowledge base</h3>
      <p className="muted small">The AI assistant will use this answer for similar questions, this term and the next. Remove anything personal first.</p>
      <label className="block" htmlFor={`sq-${thread.id}`}>Question</label>
      <textarea id={`sq-${thread.id}`} rows={2} maxLength={2000} value={q} onChange={(e) => setQ(e.target.value)} />
      <label className="block" htmlFor={`sa-${thread.id}`}>Answer</label>
      <textarea id={`sa-${thread.id}`} rows={4} maxLength={6000} value={a} onChange={(e) => setA(e.target.value)} />
      <label className="checkline"><input type="checkbox" checked={faq} onChange={(e) => setFaq(e.target.checked)} />
        Also publish to the course FAQ (every student sees it, without the asker’s name)</label>
      <ErrorText error={error} />
      <button className="primary" disabled={busy || q.trim().length < 3 || !a.trim()}
              onClick={() => run(async () => { await api.qnaSave(thread.id, { question: q, answer: a, faq }); onSaved() })}>
        Save
      </button>
    </div>
  )
}

function InboxThread({ id, onChange }) {
  const [t, setT] = useState(null)
  const [reply, setReply] = useState('')
  const { busy, error, run } = useAction()
  const load = useCallback(() => api.qnaThread(id).then(setT), [id])
  useEffect(() => { load() }, [load])
  if (!t) return <Loading />
  const send = (resolve) => run(async () => { setT(await api.qnaReply(t.id, reply.trim(), resolve)); setReply(''); onChange() })
  const hasStaffReply = t.messages.some((m) => m.role === 'staff')
  return (
    <div className="qna-inbox-thread">
      <div className="row-between">
        <div>
          <h3 className="ga-title">{t.title}</h3>
          <span className="muted small">{t.student.name} · {t.student.email} · {t.category_label}{t.is_preview ? ' · preview' : ''}</span>
        </div>
        <QnaStatus status={t.status} />
      </div>
      <div className="card qna-log">{t.messages.map((m) => <QnaMessage key={m.id} m={m} studentLabel={t.student.name} />)}</div>
      <label htmlFor={`reply-${t.id}`} className="block"><strong>Reply to {t.student.name}</strong></label>
      <textarea id={`reply-${t.id}`} rows={4} maxLength={6000} value={reply} onChange={(e) => setReply(e.target.value)} style={{ width: '100%' }} />
      <ErrorText error={error} />
      <div className="inline wrap">
        <button className="primary" disabled={busy || !reply.trim()} onClick={() => send(true)}>Send and mark resolved</button>
        <button className="secondary" disabled={busy || !reply.trim()} onClick={() => send(false)}>Send</button>
        {t.status !== 'resolved' && hasStaffReply && (
          <button className="link" disabled={busy} onClick={() => run(async () => { setT(await api.qnaResolve(t.id)); onChange() })}>Mark resolved</button>
        )}
      </div>
      {hasStaffReply && (t.saved ? <Banner>This answer is saved in the knowledge base.</Banner>
        : <SaveToKnowledge thread={t} onSaved={() => { load(); onChange() }} />)}
    </div>
  )
}

function Inbox({ course }) {
  const [data, setData] = useState(null)
  const [open, setOpen] = useState(null)
  const load = useCallback(() => api.qnaInbox(course.id).then(setData), [course.id])
  useEffect(() => { load() }, [load])
  if (!data) return <Loading />
  const s = data.stats
  return (
    <div>
      <p className="muted">
        {s.questions} questions so far · {s.ai_only} answered by the AI alone · {s.escalated} sent to staff · {s.waiting} waiting for a reply.
        {' '}Only questions sent to staff appear here; you never see the rest of a student’s questions.
      </p>
      {!data.threads.length ? <div className="empty card"><p>No questions have been sent to the staff yet.</p></div> : (
        <div className="qna-inbox">
          <ul className="qna-inbox-list">
            {data.threads.map((t) => (
              <li key={t.id}>
                <button className={`pick ${open === t.id ? 'active' : ''}`} onClick={() => setOpen(t.id)}>
                  <span><strong>{t.title}</strong><span className="muted small block">{t.student.name} · {t.category_label} · {day(t.updated_at)}</span></span>
                  <QnaStatus status={t.status} />
                </button>
              </li>
            ))}
          </ul>
          <div>{open ? <InboxThread key={open} id={open} onChange={load} /> : <p className="muted">Pick a question to read and reply.</p>}</div>
        </div>
      )}
    </div>
  )
}

function PairRow({ course, p, onChange }) {
  const [editing, setEditing] = useState(p.status === 'pending')
  const [q, setQ] = useState(p.question)
  const [a, setA] = useState(p.answer)
  const { busy, error, run } = useAction()
  const save = (extra = {}) => run(async () => { await api.updateQnaPair(course.id, p.id, { question: q, answer: a, ...extra }); onChange() })
  return (
    <div className={`card qna-pair ${p.status}`}>
      {editing ? (
        <>
          <label className="block" htmlFor={`pq-${p.id}`}>Question</label>
          <textarea id={`pq-${p.id}`} rows={2} maxLength={2000} value={q} onChange={(e) => setQ(e.target.value)} />
          <label className="block" htmlFor={`pa-${p.id}`}>Answer</label>
          <textarea id={`pa-${p.id}`} rows={3} maxLength={6000} value={a} onChange={(e) => setA(e.target.value)} />
        </>
      ) : (
        <><strong>{p.question}</strong><Markdown text={p.answer} /></>
      )}
      <ErrorText error={error} />
      <div className="inline wrap">
        {p.status === 'pending' ? (
          <button className="primary small" disabled={busy} onClick={() => save({ status: 'approved' })}>Approve</button>
        ) : editing ? (
          <button className="primary small" disabled={busy} onClick={() => save().then(() => setEditing(false))}>Save</button>
        ) : (
          <button className="secondary small" onClick={() => setEditing(true)}>Edit</button>
        )}
        {p.status === 'approved' && (
          <label className="checkline small">
            <input type="checkbox" checked={p.faq} disabled={busy}
                   onChange={(e) => run(async () => { await api.updateQnaPair(course.id, p.id, { faq: e.target.checked }); onChange() })} />
            On the student FAQ
          </label>
        )}
        <button className="link small" disabled={busy} onClick={() => run(async () => { await api.deleteQnaPair(course.id, p.id); onChange() })}>Delete</button>
        {p.thread_id && <Badge tone="info">From a staff reply</Badge>}
      </div>
    </div>
  )
}

function Knowledge({ course, cfg }) {
  const [data, setData] = useState(null)
  const [files, setFiles] = useState([])
  const [rights, setRights] = useState(false)
  const [filter, setFilter] = useState('')
  const [manual, setManual] = useState({ question: '', answer: '', faq: false })
  const upload = useAction()
  const add = useAction()
  const approve = useAction()
  const load = useCallback(() => api.qnaKnowledge(course.id).then(setData), [course.id])
  useEffect(() => { load() }, [load])
  const processing = data?.sources.some((s) => s.status === 'processing')
  useEffect(() => {
    if (!processing) return undefined
    const t = setInterval(load, 3000)
    return () => clearInterval(t)
  }, [processing, load])
  if (!data) return <Loading />
  const pending = data.pairs.filter((p) => p.status === 'pending')
  const f = filter.trim().toLowerCase()
  const approved = data.pairs.filter((p) => p.status === 'approved' && (!f || `${p.question} ${p.answer}`.toLowerCase().includes(f)))
  const send = () => upload.run(async () => {
    const form = new FormData()
    form.append('rights', rights ? 'true' : 'false')
    files.forEach((x) => form.append('files', x))
    await api.uploadQnaSources(course.id, form)
    setFiles([])
    await load()
  })
  return (
    <div>
      <div className="card">
        <h3>Upload past Q&amp;A</h3>
        <p className="muted small">
          Old forum exports, FAQ sheets, emails saved as documents: PDF, Word (.docx), .txt or .md, up to {cfg?.upload?.max_mb || 20} MB each.
          The AI pulls out question and answer pairs and removes names; nothing is used until you approve it.
        </p>
        <input type="file" multiple accept=".pdf,.docx,.txt,.md" aria-label="Q&A documents"
               onChange={(e) => setFiles([...e.target.files])} />
        <label className="checkline"><input type="checkbox" checked={rights} onChange={(e) => setRights(e.target.checked)} />
          I have the right to use these documents, and they contain no private student information I can’t share with the AI service</label>
        <ErrorText error={upload.error} />
        <button className="primary" disabled={upload.busy || !files.length || !rights} onClick={send}>{upload.busy ? 'Uploading…' : 'Upload'}</button>
        {data.sources.length > 0 && (
          <div className="tablewrap" style={{ marginTop: 12 }}>
            <table className="table">
              <thead><tr><th>Document</th><th>Status</th><th>Pairs found</th><th /></tr></thead>
              <tbody>{data.sources.map((s) => (
                <tr key={s.id}>
                  <td><span className="doctitle">{s.file_name}</span><span className="muted small block">{when(s.created_at)}</span></td>
                  <td>{s.status === 'ready' ? <Badge tone="good">Ready</Badge> : s.status === 'processing' ? <Badge tone="info">Reading…</Badge>
                    : <Badge tone="bad">{s.status === 'no_text' ? 'No text found' : 'Failed'}</Badge>}
                    {s.status_detail && <span className="muted small block">{s.status_detail}</span>}</td>
                  <td>{s.pairs_found}</td>
                  <td><button className="link small" onClick={async () => { await api.deleteQnaSource(course.id, s.id); load() }}>Remove</button></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </div>

      {pending.length > 0 && (
        <section>
          <div className="row-between">
            <h3>Waiting for review ({pending.length})</h3>
            <button className="secondary" disabled={approve.busy} onClick={() => approve.run(async () => { await api.approveQnaPairs(course.id); load() })}>
              Approve all
            </button>
          </div>
          <ErrorText error={approve.error} />
          {pending.map((p) => <PairRow key={p.id} course={course} p={p} onChange={load} />)}
        </section>
      )}

      <section>
        <div className="row-between">
          <h3>Knowledge base ({data.pairs.length - pending.length} approved)</h3>
          <input type="search" placeholder="Filter…" aria-label="Filter Q&A pairs" value={filter} onChange={(e) => setFilter(e.target.value)} />
        </div>
        <div className="card qna-pair">
          <strong>Add a Q&amp;A pair</strong>
          <textarea aria-label="Question" rows={2} maxLength={2000} placeholder="Question" value={manual.question}
                    onChange={(e) => setManual({ ...manual, question: e.target.value })} />
          <textarea aria-label="Answer" rows={3} maxLength={6000} placeholder="Answer" value={manual.answer}
                    onChange={(e) => setManual({ ...manual, answer: e.target.value })} />
          <label className="checkline"><input type="checkbox" checked={manual.faq} onChange={(e) => setManual({ ...manual, faq: e.target.checked })} /> Publish to the student FAQ</label>
          <ErrorText error={add.error} />
          <button className="primary small" disabled={add.busy || manual.question.trim().length < 3 || !manual.answer.trim()}
                  onClick={() => add.run(async () => { await api.addQnaPair(course.id, manual); setManual({ question: '', answer: '', faq: false }); load() })}>
            Add
          </button>
        </div>
        {approved.length ? approved.map((p) => <PairRow key={p.id} course={course} p={p} onChange={load} />)
          : <p className="muted">No approved pairs{f ? ' match' : ' yet'}.</p>}
      </section>
    </div>
  )
}

function Rules({ course }) {
  const [rules, setRules] = useState(null)
  const [saved, setSaved] = useState(false)
  const { busy, error, run } = useAction()
  useEffect(() => { api.qnaRules(course.id).then(setRules) }, [course.id])
  if (!rules) return <Loading />
  const set = (patch) => { setSaved(false); setRules({ ...rules, ...patch }) }
  return (
    <div className="card">
      <label className="checkline"><input type="checkbox" checked={rules.enabled} onChange={(e) => set({ enabled: e.target.checked })} />
        <strong>AI assistant answers questions</strong> (off: every question goes straight to the staff inbox)</label>
      <div className="tablewrap" style={{ marginTop: 12 }}>
        <table className="table">
          <thead><tr><th>Kind of question</th><th>Who answers</th></tr></thead>
          <tbody>{Object.entries(rules.labels).map(([k, label]) => (
            <tr key={k}>
              <td>{label}</td>
              <td>
                <select aria-label={`Who answers: ${label}`} value={rules.categories[k]} disabled={!rules.enabled}
                        onChange={(e) => set({ categories: { ...rules.categories, [k]: e.target.value } })}>
                  <option value="answer">AI assistant (students can still escalate)</option>
                  <option value="escalate">Always the course staff</option>
                </select>
              </td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      <label htmlFor="qna-instructions" className="block"><strong>Instructions for the assistant</strong>
        <span className="muted small"> ({rules.instructions.length} / 4000)</span></label>
      <textarea id="qna-instructions" rows={6} maxLength={4000} value={rules.instructions} style={{ width: '100%' }}
                placeholder={'For example:\nOffice hours are Tuesdays 3–5 pm in MS 6229.\nNever confirm exam dates; point students to the syllabus.\nFor regrade questions, students must submit on Gradescope within a week.'}
                onChange={(e) => set({ instructions: e.target.value })} />
      <p className="muted small">Instructions shape scope and tone. They can’t unlock solutions or change a problem set’s mode: Graded sets stay hints-only here too.</p>
      <ErrorText error={error} />
      <div className="inline">
        <button className="primary" disabled={busy} onClick={() => run(async () => { setRules(await api.saveQnaRules(course.id, rules)); setSaved(true) })}>Save rules</button>
        {saved && <span className="muted small" role="status">Saved.</span>}
      </div>
    </div>
  )
}

const VIEWS = [['inbox', 'Inbox'], ['knowledge', 'Knowledge base'], ['rules', 'Rules']]

export default function QnA({ course, cfg }) {
  const [view, setView] = useState('inbox')
  return (
    <div>
      <h2>AI teaching assistant</h2>
      <p className="muted">
        Students ask the course questions; the assistant answers from your Q&amp;A knowledge base and materials, within your
        rules, and sends the rest to this inbox for any staff member to answer. Save good answers so next term’s TAs start
        with them.
      </p>
      <div className="pane-tabs qna-views" role="tablist">
        {VIEWS.map(([k, label]) => (
          <button key={k} role="tab" aria-selected={view === k} className={`pane-tab ${view === k ? 'active' : ''}`} onClick={() => setView(k)}>{label}</button>
        ))}
      </div>
      {view === 'inbox' && <Inbox course={course} />}
      {view === 'knowledge' && <Knowledge course={course} cfg={cfg} />}
      {view === 'rules' && <Rules course={course} />}
    </div>
  )
}
