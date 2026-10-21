import { useState } from 'react'
import { api } from './api.js'
import { navigate } from './router.js'
import { ErrorText, useAction } from './ui.jsx'

// For someone with no courses (or choosing "Join or create a course…"): enter a code, or create a course.
export default function Welcome({ me, onJoined }) {
  const [code, setCode] = useState('')
  const { busy, error, run } = useAction()

  const join = (e) => {
    e.preventDefault()
    run(async () => {
      const r = await api.join(code.trim())
      await onJoined()
      navigate(`/c/${r.course_id}`)
    })
  }

  return (
    <div className="narrow">
      <h1>{me.courses.length ? 'Join or create a course' : `Welcome, ${me.name}`}</h1>
      <div className="cards two">
        <form className="card" onSubmit={join}>
          <h2>Join a course</h2>
          <p className="muted">Enter the code your instructor shared. TAs and co-instructors: enter your staff code here too.</p>
          <label htmlFor="code">Course code</label>
          <input id="code" className="mono" value={code} onChange={(e) => setCode(e.target.value)} placeholder="ABCD-2345"
                 autoComplete="off" autoCapitalize="characters" spellCheck={false} />
          <ErrorText error={error} />
          <button className="primary" type="submit" disabled={busy || code.trim().length < 4}>{busy ? 'Joining…' : 'Join'}</button>
        </form>
        <div className="card">
          <h2>Create a course</h2>
          <p className="muted">For instructors: set up BruinBuddy for your class, upload your materials, and share a code with students.</p>
          <button className="secondary" onClick={() => navigate('/create')}>Create a course</button>
        </div>
      </div>
    </div>
  )
}
