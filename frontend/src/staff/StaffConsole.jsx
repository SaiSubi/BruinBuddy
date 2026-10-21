import { navigate } from '../router.js'
import { money, ROLE } from '../format.js'
import { Banner, ErrorText, useAction } from '../ui.jsx'
import { startCheckout, TestModeNote } from '../CreateCourse.jsx'
import Setup from './Setup.jsx'
import Materials from './Materials.jsx'
import ProblemSets from './ProblemSets.jsx'
import Guidelines from './Guidelines.jsx'
import Members from './Members.jsx'
import Dashboard from './Dashboard.jsx'
import Pause from './Pause.jsx'
import Plan from './Plan.jsx'

const TABS = [
  ['setup', 'Setup'], ['materials', 'Materials'], ['problem-sets', 'Problem sets'], ['guidelines', 'Guidelines'],
  ['members', 'Members'], ['dashboard', 'Dashboard'], ['pause', 'Pause'], ['plan', 'Plan & limits'],
]

function PendingCourse({ course, cfg }) {
  const { busy, error, run } = useAction()
  return (
    <div className="narrow">
      <h1>{course.name}</h1>
      <div className="card">
        <h2>Finish payment to open your course</h2>
        <p>Your course is saved but not active yet. Students can join once payment is confirmed.</p>
        <p className="bigprice">{money(course.billing?.price_cents || 0)}</p>
        <TestModeNote cfg={cfg} />
        <ErrorText error={error} />
        <button className="primary" disabled={busy} onClick={() => run(() => startCheckout(course.id))}>
          {busy ? 'Opening checkout…' : 'Pay with Stripe'}
        </button>
      </div>
    </div>
  )
}

export default function StaffConsole({ course, tab, reload, cfg }) {
  if (course.status === 'pending') return <PendingCourse course={course} cfg={cfg} />
  const props = { course, reload, cfg }
  const panels = {
    setup: <Setup {...props} />, materials: <Materials {...props} />, 'problem-sets': <ProblemSets {...props} />,
    guidelines: <Guidelines {...props} />, members: <Members {...props} />, dashboard: <Dashboard {...props} />,
    pause: <Pause {...props} />, plan: <Plan {...props} />,
  }
  return (
    <div className="console">
      <div className="console-head">
        <div>
          <h1>{course.name}</h1>
          <span className="muted small">{ROLE[course.role]} · student code <code>{course.student_code}</code></span>
        </div>
        <button className="secondary" onClick={() => navigate(`/c/${course.id}/preview`)}>Preview as student</button>
      </div>
      <nav className="tabs" aria-label="Course sections">
        {TABS.map(([key, label]) => (
          <a key={key} className={`tab ${tab === key ? 'active' : ''}`} aria-current={tab === key ? 'page' : undefined}
             href={`#/c/${course.id}/staff/${key}`}>{label}</a>
        ))}
      </nav>
      {course.pause?.active && <Banner kind="warning">The tutor is paused for students right now (Pause tab).</Banner>}
      <section className="tabpanel">{panels[tab] || panels.setup}</section>
    </div>
  )
}
