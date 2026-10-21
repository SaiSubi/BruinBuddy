import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import { fromLocalInput, toLocalInput, when } from '../format.js'
import { Badge, Banner, ErrorText, Loading, useAction } from '../ui.jsx'
import { modeTone } from '../CourseHome.jsx'

const MODES = [
  ['graded', 'Graded: hints only'],
  ['practice', 'Practice: full help'],
  ['open', 'Solutions open'],
]

function SetRow({ p, course, reload }) {
  const [release, setRelease] = useState(toLocalInput(p.release_at))
  const { busy, error, run } = useAction()
  const save = (body) => run(async () => { await api.updateMaterial(course.id, p.id, body); await reload() })
  const released = p.mode !== 'open' && p.effective_mode === 'open'
  return (
    <tr>
      <td>
        <span className="doctitle">{p.title}</span>
        <span className="block"><Badge tone={modeTone(p.effective_mode)}>Students see: {p.mode_label}</Badge></span>
        {released && <span className="muted small block">Opened automatically on {when(p.release_at)}.</span>}
        <ErrorText error={error} />
      </td>
      <td>
        <select aria-label={`Mode for ${p.title}`} value={p.mode} disabled={busy} onChange={(e) => save({ mode: e.target.value })}>
          {MODES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
      </td>
      <td>
        <div className="inline">
          <input type="datetime-local" aria-label={`Release date for ${p.title}`} value={release}
                 onChange={(e) => setRelease(e.target.value)} />
          <button className="secondary small" disabled={busy} onClick={() => save({ release_at: fromLocalInput(release) })}>Save</button>
          {p.release_at && <button className="link small" disabled={busy} onClick={() => { setRelease(''); save({ release_at: null }) }}>Clear</button>}
        </div>
      </td>
      <td>
        <label className="checkline">
          <input type="checkbox" checked={p.confirm_answers} disabled={busy || p.effective_mode === 'open'}
                 onChange={(e) => save({ confirm_answers: e.target.checked })} /> Tell students if their final answer is correct
        </label>
      </td>
      <td>
        {p.solutions.length ? p.solutions.map((s) => <span key={s.id} className="block small">{s.title}</span>)
          : <span className="muted small">No solution linked</span>}
      </td>
    </tr>
  )
}

export default function ProblemSets({ course, reload: reloadCourse }) {
  const [items, setItems] = useState(null)
  const confirm = useAction()
  const load = useCallback(() => api.materials(course.id).then((r) => setItems(r.materials.filter((m) => m.kind === 'problem_set'))), [course.id])
  useEffect(() => { load() }, [load])
  if (!items) return <Loading />
  const confirmed = course.setup.find((s) => s.step === 'modes')?.done
  return (
    <div>
      <h2>Problem set modes</h2>
      <p className="muted">
        Every student gets the same rule for a set, shown in their chat. <strong>Graded</strong>: hints and questions only,
        never final answers or solution steps. <strong>Practice</strong>: a worked explanation after an attempt or on
        request; the solution file stays hidden. <strong>Solutions open</strong>: linked solutions become visible and citable.
        A release date switches a Graded set to open automatically. Changes apply from the next message.
      </p>
      {!items.length ? (
        <div className="empty card"><p>No problem sets yet. Upload them in Materials with the “Problem set” category.</p></div>
      ) : (
        <div className="tablewrap">
          <table className="table">
            <thead><tr><th>Problem set</th><th>Mode</th><th>Release date (optional)</th><th>Answer check</th><th>Solutions</th></tr></thead>
            <tbody>{items.map((p) => <SetRow key={p.id} p={p} course={course} reload={load} />)}</tbody>
          </table>
        </div>
      )}
      <p className="muted small">For exams, use Pause instead: detecting a pasted exam question isn’t reliable.</p>
      {confirmed ? <Banner>Modes confirmed. You can change them any time.</Banner> : (
        <button className="primary" disabled={confirm.busy}
                onClick={() => confirm.run(async () => { await api.setupStep(course.id, 'modes'); reloadCourse() })}>
          Confirm modes
        </button>
      )}
      <ErrorText error={confirm.error} />
    </div>
  )
}
