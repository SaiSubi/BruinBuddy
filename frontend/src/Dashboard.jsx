import { useEffect, useState } from 'react'
import { api } from './api.js'

export default function Dashboard({ user, onSignOut, onAbout }) {
  const [count, setCount] = useState(null)
  useEffect(() => {
    api.dashboard().then((d) => setCount(d.questions_asked)).catch(() => setCount('—'))
  }, [])
  return (
    <div className="page">
      <header className="topbar">
        <strong>BruinBuddy · Professor</strong>
        <span className="spacer" />
        <button className="link" onClick={onAbout}>About</button>
        <span className="muted">{user.name}</span>
        <button className="link" onClick={onSignOut}>Sign out</button>
      </header>
      <main className="dash">
        <p className="muted">Questions asked</p>
        <p className="bignum" aria-live="polite">{count ?? '…'}</p>
      </main>
    </div>
  )
}
