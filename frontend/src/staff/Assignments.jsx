import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import { day, when } from '../format.js'
import { Badge, Banner, ErrorText, Loading, Modal, useAction } from '../ui.jsx'
import { Markdown } from '../Message.jsx'

const BLANK = { title: '', prompt: '', target_answer: '', rubric: '', hint: '', points: 25 }
const MAX_CHECKPOINTS = 8
const STATUS_TONE = { passed: 'good', active: 'info', skipped: 'warn', locked: 'neutral' }

function CheckpointEditor({ cp, i, count, onChange, onMove, onRemove }) {
  const set = (key) => (e) => onChange({ ...cp, [key]: key === 'points' ? Number(e.target.value) : e.target.value })
  const id = (key) => `cp-${i}-${key}`
  return (
    <div className="card ga-cp-editor">
      <div className="row-between">
        <strong>Checkpoint {i + 1}{i === count - 1 ? ' (final answer)' : ''}</strong>
        <div className="inline">
          <button type="button" className="link small" disabled={i === 0} onClick={() => onMove(i, -1)}>Move up</button>
          <button type="button" className="link small" disabled={i === count - 1} onClick={() => onMove(i, 1)}>Move down</button>
          <button type="button" className="link small" disabled={count === 1} onClick={() => onRemove(i)}>Remove</button>
        </div>
      </div>
      <div className="form-grid compact">
        <label htmlFor={id('title')}>Title</label>
        <input id={id('title')} value={cp.title} maxLength={160} onChange={set('title')} />
        <label htmlFor={id('prompt')}>Question for the student</label>
        <textarea id={id('prompt')} rows={2} value={cp.prompt} maxLength={2000} onChange={set('prompt')} />
        <label htmlFor={id('target')}>Target answer <span className="muted small">(hidden until reached)</span></label>
        <input id={id('target')} value={cp.target_answer} maxLength={2000} onChange={set('target_answer')} />
        <label htmlFor={id('rubric')}>Rubric <span className="muted small">(never shown to students)</span></label>
        <textarea id={id('rubric')} rows={2} value={cp.rubric} maxLength={2000} onChange={set('rubric')} />
        <label htmlFor={id('hint')}>Hint <span className="muted small">(given on request)</span></label>
        <input id={id('hint')} value={cp.hint} maxLength={1000} onChange={set('hint')} />
        <label htmlFor={id('points')}>Points</label>
        <input id={id('points')} type="number" min={0} max={1000} value={cp.points} onChange={set('points')} />
      </div>
    </div>
  )
}

function Builder({ course, onPublished, onCancel }) {
  const [draft, setDraft] = useState({ title: '', problem_statement: '', solution_notes: '' })
  const [checkpoints, setCheckpoints] = useState([])
  const gen = useAction()
  const pub = useAction()
  const set = (key) => (e) => setDraft({ ...draft, [key]: e.target.value })
  const total = checkpoints.reduce((s, c) => s + (Number(c.points) || 0), 0)
  const ready = draft.title.trim() && draft.problem_statement.trim()
  const complete = checkpoints.length > 0 && checkpoints.every((c) => c.title.trim() && c.prompt.trim() && c.target_answer.trim())

  const generate = () => gen.run(async () => {
    const r = await api.generateCheckpoints(course.id, draft)
    setCheckpoints(r.checkpoints.map(({ index, ...c }) => c))
  })
  const publish = () => pub.run(async () => {
    await api.createAssignment(course.id, { ...draft, checkpoints })
    onPublished()
  })
  const move = (i, d) => setCheckpoints((cs) => {
    const next = [...cs]
    ;[next[i], next[i + d]] = [next[i + d], next[i]]
    return next
  })

  return (
    <div className="ga-builder">
      <h2>New AI-guided assignment</h2>
      <div className="card">
        <div className="form-grid">
          <label htmlFor="ga-title">Title</label>
          <input id="ga-title" value={draft.title} maxLength={120} onChange={set('title')} placeholder="e.g. Bayes with two coins" />
          <label htmlFor="ga-problem">Problem statement <span className="muted small">(shown to students; LaTeX with $…$)</span></label>
          <textarea id="ga-problem" rows={5} value={draft.problem_statement} maxLength={8000} onChange={set('problem_statement')} />
          <label htmlFor="ga-notes">Solution notes <span className="muted small">(never shown to students or the tutor)</span></label>
          <textarea id="ga-notes" rows={5} value={draft.solution_notes} maxLength={8000} onChange={set('solution_notes')} />
        </div>
        <div className="inline wrap">
          <button className="primary" disabled={!ready || gen.busy} onClick={generate}>
            {gen.busy ? 'Drafting checkpoints…' : checkpoints.length ? 'Regenerate checkpoints with AI' : 'Auto-generate checkpoints with AI'}
          </button>
          <button className="secondary" disabled={checkpoints.length >= MAX_CHECKPOINTS}
                  onClick={() => setCheckpoints((cs) => [...cs, { ...BLANK }])}>
            Add a checkpoint by hand
          </button>
        </div>
        <ErrorText error={gen.error} />
        {checkpoints.length > 0 && <p className="muted small">Review every checkpoint before publishing: the AI drafts, you decide.</p>}
      </div>

      {checkpoints.map((cp, i) => (
        <CheckpointEditor key={i} cp={cp} i={i} count={checkpoints.length}
                          onChange={(c) => setCheckpoints((cs) => cs.map((x, j) => (j === i ? c : x)))}
                          onMove={move} onRemove={(j) => setCheckpoints((cs) => cs.filter((_, k) => k !== j))} />
      ))}

      <div className="row-between">
        <span className="muted">{checkpoints.length} checkpoint(s) · {total} points in total</span>
        <div className="inline">
          <button className="secondary" onClick={onCancel}>Cancel</button>
          <button className="primary" disabled={!ready || !complete || total <= 0 || pub.busy} onClick={publish}>
            {pub.busy ? 'Publishing…' : 'Publish assignment'}
          </button>
        </div>
      </div>
      <ErrorText error={pub.error} />
    </div>
  )
}

function Gradebook({ assignment, onClose }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => { api.assignmentSubmissions(assignment.id).then(setData).catch(setError) }, [assignment.id])
  const titles = assignment.checkpoints.map((c) => c.title)
  return (
    <Modal title={`Gradebook: ${assignment.title}`} onClose={onClose} wide>
      <ErrorText error={error} />
      {!data && !error ? <Loading /> : data && !data.submissions.length ? (
        <p className="muted">No students have opened this assignment yet.</p>
      ) : data && (
        <>
          <div className="tablewrap">
            <table className="table">
              <thead>
                <tr><th>Student</th><th>Status</th><th>Score</th>{titles.map((t, i) => <th key={i}>{i + 1}</th>)}<th>Last activity</th></tr>
              </thead>
              <tbody>
                {data.submissions.map((s) => (
                  <tr key={s.user_id}>
                    <td><span className="doctitle">{s.name}</span><span className="muted small block">{s.email}</span></td>
                    <td>{s.status === 'completed' ? <Badge tone="good">Completed</Badge> : <Badge tone="info">In progress</Badge>}</td>
                    <td>{s.score} / {assignment.total_points}</td>
                    {s.checkpoints.map((c) => (
                      <td key={c.index}><Badge tone={STATUS_TONE[c.status]}>{c.status}</Badge>
                        <span className="muted small block">{c.earned_points} pts · {c.attempts || 0} tries</span></td>
                    ))}
                    <td className="small">{when(s.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <h3>Transcripts</h3>
          {data.submissions.map((s) => (
            <details key={s.user_id} className="ga-transcript">
              <summary>{s.name} · {s.messages.length} messages</summary>
              {s.messages.map((m) => (
                <div key={m.id} className={`ga-transcript-msg ${m.role}`}>
                  <span className="muted small">{m.role === 'user' ? s.name : 'BruinBuddy'} · checkpoint {m.checkpoint_index + 1}
                    {m.event_type === 'skip' ? ' · skipped' : m.event_type === 'leak_blocked' ? ' · reply replaced by leak guard' : ''}</span>
                  <Markdown text={m.content} />
                </div>
              ))}
            </details>
          ))}
        </>
      )}
    </Modal>
  )
}

export default function Assignments({ course }) {
  const [items, setItems] = useState(null)
  const [building, setBuilding] = useState(false)
  const [book, setBook] = useState(null)
  const [notice, setNotice] = useState('')
  const del = useAction()
  const load = useCallback(() => api.assignments(course.id).then(setItems), [course.id])
  useEffect(() => { load() }, [load])
  if (!items) return <Loading />

  if (building) {
    return <Builder course={course} onCancel={() => setBuilding(false)}
                    onPublished={async () => { setBuilding(false); setNotice('Assignment published. Students can open it now.'); await load() }} />
  }
  const remove = (a) => {
    if (!window.confirm(`Delete “${a.title}” and every student's progress on it? This can't be undone.`)) return
    del.run(async () => { await api.deleteAssignment(a.id); await load() })
  }
  return (
    <div>
      <div className="row-between">
        <h2>AI-guided assignments</h2>
        <button className="primary" onClick={() => { setNotice(''); setBuilding(true) }}>New assignment</button>
      </div>
      <p className="muted">
        One problem, worked through in checkpoints. The answer checker compares each step with your hidden target answer
        and rubric; the tutor only nudges and never sees an answer the student hasn’t reached. Students may skip a step for
        0 points to see its result. Unlike tutor chats, you can read assignment conversations here, and students are told so.
      </p>
      {notice && <Banner>{notice}</Banner>}
      <ErrorText error={del.error} />
      {!items.length ? (
        <div className="empty card"><p>No assignments yet. Write a problem and let the AI draft the checkpoints.</p></div>
      ) : (
        <div className="tablewrap">
          <table className="table">
            <thead><tr><th>Assignment</th><th>Checkpoints</th><th>Started</th><th>Completed</th><th>Average</th><th>Actions</th></tr></thead>
            <tbody>
              {items.map((a) => (
                <tr key={a.id}>
                  <td>
                    <span className="doctitle">{a.title}</span>
                    <span className="muted small block">Published {day(a.created_at)} · {a.total_points} pts</span>
                    <details className="small">
                      <summary>Problem and checkpoints</summary>
                      <Markdown text={a.problem_statement} />
                      <ol>{a.checkpoints.map((c) => <li key={c.index}>{c.title} ({c.points} pts): target <code>{c.target_answer}</code></li>)}</ol>
                    </details>
                  </td>
                  <td>{a.checkpoint_count}</td>
                  <td>{a.stats.started}</td>
                  <td>{a.stats.completed}</td>
                  <td>{a.stats.average_score ?? '–'}</td>
                  <td>
                    <div className="inline wrap">
                      <button className="secondary small" onClick={() => setBook(a)}>Gradebook</button>
                      <a className="secondary small btnlink" href={`#/c/${course.id}/assignments/${a.id}`}>Try as student</a>
                      <button className="link small" disabled={del.busy} onClick={() => remove(a)}>Delete</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {book && <Gradebook assignment={book} onClose={() => setBook(null)} />}
    </div>
  )
}
