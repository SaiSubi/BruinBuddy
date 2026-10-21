import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import { day, fromLocalInput, toLocalInput, tokens, when } from '../format.js'
import { Badge, CopyCode, ErrorText, Loading, Modal, useAction } from '../ui.jsx'

function AccessSettings({ course, reload }) {
  const [domain, setDomain] = useState(course.email_domain || '')
  const [expiry, setExpiry] = useState(toLocalInput(course.code_expires_at))
  const { busy, error, run } = useAction()
  const save = (body) => run(async () => { await api.updateCourse(course.id, body); await reload() })
  return (
    <div className="card">
      <h3>Student code</h3>
      <p className="muted small">One code for the whole class. Rotating it stops the old code; students who already joined keep access.</p>
      <div className="inline wrap">
        <CopyCode code={course.student_code} onCopied={() => api.setupStep(course.id, 'share').then(reload)} />
        <button className="secondary small" disabled={busy}
                onClick={() => window.confirm('Make a new student code? The current code will stop working for new students.')
                  && run(async () => { await api.rotateCode(course.id); await reload() })}>Rotate code</button>
      </div>
      <div className="form-grid compact">
        <label htmlFor="expiry">Code expires</label>
        <div className="inline">
          <input id="expiry" type="datetime-local" value={expiry} onChange={(e) => setExpiry(e.target.value)} />
          <button className="secondary small" disabled={busy} onClick={() => save({ code_expires_at: fromLocalInput(expiry) })}>Save</button>
          {course.code_expires_at && <button className="link small" onClick={() => { setExpiry(''); save({ code_expires_at: null }) }}>Never</button>}
        </div>
        <label htmlFor="domain">Only allow emails at</label>
        <div className="inline">
          <input id="domain" value={domain} placeholder="ucla.edu (optional)" onChange={(e) => setDomain(e.target.value)} />
          <button className="secondary small" disabled={busy} onClick={() => save({ email_domain: domain })}>Save</button>
        </div>
      </div>
      <p className="muted small">A domain restriction only means something when sign-up confirms email addresses.</p>
      <ErrorText error={error} />
    </div>
  )
}

function StaffCodes({ course, onChange }) {
  const [codes, setCodes] = useState([])
  const [shown, setShown] = useState(null)
  const { busy, error, run } = useAction()
  const load = useCallback(() => api.staffCodes(course.id).then(setCodes).catch(() => {}), [course.id])
  useEffect(() => { load() }, [load])
  const pending = codes.filter((c) => c.status === 'pending')
  return (
    <div className="card">
      <div className="row-between">
        <h3>Add staff</h3>
        <button className="secondary small" disabled={busy}
                onClick={() => run(async () => { setShown(await api.createStaffCode(course.id)); await load(); onChange() })}>
          Create a staff code
        </button>
      </div>
      <p className="muted small">Each code works once, for one person, for 7 days. They sign up with their own email and enter it under “Join a course”.</p>
      <ErrorText error={error} />
      {pending.length > 0 && (
        <ul className="plain">
          {pending.map((c) => (
            <li key={c.id} className="inline">
              <code>…{c.last4}</code><span className="muted small">expires {day(c.expires_at)}</span>
              <button className="link small danger" onClick={() => run(async () => { await api.revokeStaffCode(course.id, c.id); await load(); onChange() })}>Revoke</button>
            </li>
          ))}
        </ul>
      )}
      {shown && (
        <Modal title="Staff code" onClose={() => setShown(null)}>
          <p>Give this code to one person. <strong>Copy it now; you won’t see it again.</strong></p>
          <CopyCode code={shown.code} />
          <p className="muted small">Expires {when(shown.expires_at)}.</p>
        </Modal>
      )}
    </div>
  )
}

export default function Members({ course, reload }) {
  const [data, setData] = useState(null)
  const { error, run } = useAction()
  const load = useCallback(() => api.members(course.id).then(setData), [course.id])
  useEffect(() => { load() }, [load])
  const act = (userId, action, label) => {
    if (!window.confirm(label)) return
    run(async () => { await api.memberAction(course.id, userId, action); await load() })
  }
  const owner = course.role === 'owner'
  return (
    <div>
      <h2>Members</h2>
      <AccessSettings course={course} reload={reload} />
      {owner && <StaffCodes course={course} onChange={load} />}
      {!data ? <Loading /> : (
        <>
          <ErrorText error={error} />
          <h3>Staff ({data.seats.staff} of {data.seats.staff_seats} staff seats{data.seats.pending_codes ? `, ${data.seats.pending_codes} code pending` : ''})</h3>
          <ul className="plain">
            {data.staff.map((p) => (
              <li key={p.user_id} className="inline">
                <span>{p.name}</span><span className="muted small">{p.email}</span><Badge>{p.role === 'owner' ? 'Owner' : 'Staff'}</Badge>
                {owner && p.role === 'staff' && (
                  <button className="link small danger" onClick={() => act(p.user_id, 'remove', `Remove ${p.name} from the course staff?`)}>Remove</button>
                )}
              </li>
            ))}
          </ul>
          <h3>Students ({data.seats.students} of {data.seats.student_seats} seats)</h3>
          {!data.students.length ? <p className="muted">No students yet. Share the student code to invite them.</p> : (
            <div className="tablewrap">
              <table className="table">
                <thead><tr><th>Name</th><th>Email</th><th>Joined</th><th className="num">Questions</th><th className="num">Tokens</th><th>Status</th><th /></tr></thead>
                <tbody>
                  {data.students.map((p) => (
                    <tr key={p.user_id}>
                      <td>{p.name}{p.sample && <> <Badge>Sample</Badge></>}</td>
                      <td className="small">{p.email}</td>
                      <td className="small">{day(p.joined_at)}</td>
                      <td className="num">{p.questions}</td>
                      <td className="num">{tokens(p.tokens)}</td>
                      <td><Badge tone={p.status === 'active' ? 'good' : p.status === 'blocked' ? 'bad' : 'neutral'}>{p.status}</Badge></td>
                      <td className="actions">
                        {p.status === 'active' && (
                          <>
                            <button className="link small" onClick={() => act(p.user_id, 'remove', `Remove ${p.name}? Their access ends now and the seat is freed. They can rejoin with the code.`)}>Remove</button>
                            <button className="link small danger" onClick={() => act(p.user_id, 'block', `Block ${p.name}? Their access ends now and they can’t rejoin with the code.`)}>Block</button>
                          </>
                        )}
                        {p.status === 'blocked' && (
                          <button className="link small" onClick={() => act(p.user_id, 'unblock', `Unblock ${p.name}? They’ll be able to rejoin with the code.`)}>Unblock</button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="muted small">Staff see usage numbers, never students’ chats.</p>
        </>
      )}
    </div>
  )
}
