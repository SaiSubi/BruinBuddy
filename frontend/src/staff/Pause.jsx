import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import { fromLocalInput, toLocalInput, when } from '../format.js'
import { Badge, ErrorText, useAction } from '../ui.jsx'

export default function Pause({ course, reload }) {
  const [pauses, setPauses] = useState([])
  const now = Date.now() / 1000
  const [form, setForm] = useState({ starts: toLocalInput(now), ends: toLocalInput(now + 2 * 3600), message: 'The tutor is paused during the exam.' })
  const { busy, error, run } = useAction()
  const load = useCallback(() => api.pauses(course.id).then(setPauses).catch(() => {}), [course.id])
  useEffect(() => { load() }, [load])
  const done = async () => { await load(); reload() }

  const add = (e) => {
    e.preventDefault()
    run(async () => {
      await api.addPause(course.id, { starts_at: fromLocalInput(form.starts), ends_at: fromLocalInput(form.ends), message: form.message })
      await done()
    })
  }
  return (
    <div>
      <h2>Pause the tutor</h2>
      <p className="muted">For exams: during a pause window students see your message and the tutor makes no AI call. It applies to the whole course.</p>
      <form className="card form-grid" onSubmit={add}>
        <label htmlFor="starts">Starts</label>
        <input id="starts" type="datetime-local" value={form.starts} onChange={(e) => setForm({ ...form, starts: e.target.value })} required />
        <label htmlFor="ends">Ends</label>
        <input id="ends" type="datetime-local" value={form.ends} onChange={(e) => setForm({ ...form, ends: e.target.value })} required />
        <label htmlFor="msg">Message to students</label>
        <input id="msg" value={form.message} maxLength={300} onChange={(e) => setForm({ ...form, message: e.target.value })} />
        <span />
        <div>
          <ErrorText error={error} />
          <button className="primary" type="submit" disabled={busy}>Schedule pause</button>
        </div>
      </form>
      {pauses.length > 0 && (
        <ul className="plain">
          {pauses.map((p) => (
            <li key={p.id} className="inline wrap">
              <Badge tone={p.state === 'active' ? 'warn' : p.state === 'past' ? 'neutral' : 'info'}>{p.state}</Badge>
              <span>{when(p.starts_at)} to {when(p.ends_at)}</span>
              <span className="muted small">{p.message}</span>
              {p.state !== 'past' && (
                <button className="link small danger" onClick={() => run(async () => { await api.deletePause(course.id, p.id); await done() })}>
                  {p.state === 'active' ? 'End now' : 'Cancel'}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
