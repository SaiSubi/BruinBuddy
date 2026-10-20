import { useEffect, useState } from 'react'
import { api } from './api.js'

export default function SignIn({ onSignedIn }) {
  const [name, setName] = useState('')
  const [role, setRole] = useState('student')
  const [code, setCode] = useState('')
  const [cfg, setCfg] = useState({ student_code_required: false, professor_code_required: false, professor_enabled: true })
  const [error, setError] = useState('')

  useEffect(() => { api.config().then(setCfg).catch(() => {}) }, [])

  const needsCode = role === 'student' ? cfg.student_code_required : cfg.professor_code_required
  const disabled = role === 'professor' && !cfg.professor_enabled

  const submit = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    setError('')
    try {
      onSignedIn(await api.signIn(name.trim(), role, code))
    } catch (err) {
      setError(err.status === 403 ? err.message : 'Could not sign in. Is the server running?')
    }
  }

  return (
    <main className="signin">
      <form onSubmit={submit} className="card">
        <h1>BruinBuddy</h1>
        <p className="muted">Study help for 18.05 (Intro to Probability and Statistics)</p>
        <label htmlFor="name">Name</label>
        <input id="name" value={name} onChange={(e) => setName(e.target.value)} autoFocus maxLength={60} />
        <fieldset>
          <legend>I am a</legend>
          <label className="radio">
            <input type="radio" name="role" checked={role === 'student'} onChange={() => setRole('student')} /> Student
          </label>
          <label className="radio">
            <input type="radio" name="role" checked={role === 'professor'} onChange={() => setRole('professor')} /> Professor
          </label>
        </fieldset>
        {needsCode && (
          <>
            <label htmlFor="code">Access code</label>
            <input id="code" type="password" value={code} onChange={(e) => setCode(e.target.value)} autoComplete="off" />
          </>
        )}
        {disabled && <p className="muted small">Professor sign-in is not enabled on this server.</p>}
        {error && <p className="error" role="alert">{error}</p>}
        <button className="primary" type="submit" disabled={!name.trim() || disabled}>Continue</button>
        <p className="muted small">Demo sign-in. Use the same name and role to get your chats and memory back.</p>
      </form>
    </main>
  )
}
