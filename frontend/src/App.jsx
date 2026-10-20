import { useEffect, useState } from 'react'
import { api } from './api.js'
import SignIn from './SignIn.jsx'
import Chat from './Chat.jsx'
import Dashboard from './Dashboard.jsx'
import About from './About.jsx'

export default function App() {
  const [user, setUser] = useState(undefined) // undefined = loading, null = signed out
  const [showAbout, setShowAbout] = useState(false)

  useEffect(() => {
    if (!api.hasToken()) { setUser(null); return }
    api.me().then(setUser).catch(() => setUser(null))
  }, [])

  const signOut = () => {
    api.signOut()
    setUser(null)
  }

  if (user === undefined) return <p className="center-note">Loading…</p>
  if (!user) return <SignIn onSignedIn={setUser} />
  if (showAbout) return <About onBack={() => setShowAbout(false)} />
  return user.role === 'professor' ? (
    <Dashboard user={user} onSignOut={signOut} onAbout={() => setShowAbout(true)} />
  ) : (
    <Chat user={user} onSignOut={signOut} onAbout={() => setShowAbout(true)} />
  )
}
