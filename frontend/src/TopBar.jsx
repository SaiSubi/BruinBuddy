import { navigate } from './router.js'
import { ROLE } from './format.js'

export default function TopBar({ me, courseId, onLogOut }) {
  const onSwitch = (e) => {
    const v = e.target.value
    navigate(v === 'new' ? '/join' : `/c/${v}`)
  }
  return (
    <header className="topbar">
      <a className="brand" href="#/" aria-label="BruinBuddy home">BruinBuddy</a>
      {me.courses.length > 0 && (
        <select className="switcher" aria-label="Switch course" value={courseId || ''} onChange={onSwitch}>
          {!courseId && <option value="">Choose a course</option>}
          {me.courses.map((c) => (
            <option key={c.id} value={c.id}>{c.name}{c.role !== 'student' ? ` · ${ROLE[c.role]}` : ''}{c.status === 'pending' ? ' (unpaid)' : ''}</option>
          ))}
          <option value="new">Join or create a course…</option>
        </select>
      )}
      <span className="spacer" />
      <a className="link hide-narrow" href="#/about">About</a>
      <span className="muted hide-narrow who-name">{me.name}</span>
      <button className="link" onClick={onLogOut}>Log out</button>
    </header>
  )
}
