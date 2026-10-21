import { useState } from 'react'
import { api } from './api.js'
import { navigate } from './router.js'
import { Badge, ErrorText, useAction } from './ui.jsx'

// Role-segregated onboarding screen:
// - Students only see "Join a course" with their instructor's class code (no course creation option).
// - Instructors / Professors / Tutors see "Create a course" plus "Join an existing course with a staff code".
export default function Welcome({ me, onJoined }) {
  const [code, setCode] = useState('')
  const { busy, error, run } = useAction()
  const isStudent = me?.account_type === 'student'

  const join = (e) => {
    e.preventDefault()
    run(async () => {
      const r = await api.join(code.trim())
      await onJoined()
      navigate(`/c/${r.course_id}`)
    })
  }

  if (isStudent) {
    return (
      <div className="narrow">
        <div className="row-between" style={{ marginBottom: 8 }}>
          <h1>{me.courses.length ? 'Join a course' : `Welcome, ${me.name}`}</h1>
          <Badge tone="info">Student Account</Badge>
        </div>
        <form className="card" onSubmit={join}>
          <h2>Enter your course code</h2>
          <p className="muted">
            Enter the course code your professor or instructor shared on the syllabus to unlock the AI Tutor,
            Problem Sets, and Illustrate Studio for your class.
          </p>
          <label htmlFor="code">Course code</label>
          <input
            id="code"
            className="mono"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="ABCD-2345"
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
          />
          <ErrorText error={error} />
          <button className="primary" type="submit" disabled={busy || code.trim().length < 4}>
            {busy ? 'Joining…' : 'Join Course'}
          </button>
        </form>
      </div>
    )
  }

  return (
    <div className="narrow">
      <div className="row-between" style={{ marginBottom: 8 }}>
        <h1>{me.courses.length ? 'Create or join a course' : `Welcome, ${me.name}`}</h1>
        <Badge tone="good">Instructor / Tutor Account</Badge>
      </div>
      <div className="cards two">
        <div className="card">
          <h2>Create a course</h2>
          <p className="muted">
            Set up BruinBuddy for your class, upload lecture notes and problem sets, configure solution guards, and share a join code with your students.
          </p>
          <button className="primary" type="button" onClick={() => navigate('/create')}>
            Create a course
          </button>
        </div>
        <form className="card" onSubmit={join}>
          <h2>Join with a staff or course code</h2>
          <p className="muted">
            Co-instructors, TAs, and tutors: enter the one-time staff invite code (`STAFF-...`) shared by the course owner.
          </p>
          <label htmlFor="code">Staff or course code</label>
          <input
            id="code"
            className="mono"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="STAFF-ABCD-2345-6789"
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
          />
          <ErrorText error={error} />
          <button className="secondary" type="submit" disabled={busy || code.trim().length < 4}>
            {busy ? 'Joining…' : 'Join with Code'}
          </button>
        </form>
      </div>
    </div>
  )
}
