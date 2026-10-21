import { api } from '../api.js'
import { navigate } from '../router.js'
import { Banner, CopyCode } from '../ui.jsx'

const STEPS = {
  materials: { title: 'Upload materials', text: 'Lecture notes, readings and problem sets, with solutions linked to their sets.', tab: 'materials' },
  modes: { title: 'Set problem set modes', text: 'New sets start as Graded: hints only. Choose Practice or Solutions open where you want more help.', tab: 'problem-sets' },
  guidelines: { title: 'Write guidelines', text: 'Tone, tools and notation, and what’s in or out of scope.', tab: 'guidelines' },
  preview: { title: 'Try it as a student', text: 'Ask a few questions the way a student would. Preview chats aren’t counted in the dashboard.' },
  share: { title: 'Share the student code', text: 'Share it in class or on Bruin Learn. Students join free.' },
}

export default function Setup({ course, reload }) {
  const markShared = async () => { await api.setupStep(course.id, 'share'); reload() }
  return (
    <div>
      <h2>Set up your course</h2>
      {!course.open && <Banner kind="warning">Students will see “the tutor isn’t open yet” until at least one material is ready.</Banner>}
      <ol className="checklist">
        {course.setup.map(({ step, done, detail }) => {
          const s = STEPS[step]
          return (
            <li key={step} className={done ? 'done' : ''}>
              <span className="check" aria-label={done ? 'Done' : 'Not done'}>{done ? '✓' : '○'}</span>
              <div className="check-body">
                <strong>{s.title}</strong>
                <span className="muted small">{s.text}{detail && step !== 'share' ? ` (${detail})` : ''}</span>
                {step === 'share' && <CopyCode code={course.student_code} onCopied={markShared} />}
              </div>
              <div className="check-action">
                {s.tab && <a className="secondary small btnlink" href={`#/c/${course.id}/staff/${s.tab}`}>Open</a>}
                {step === 'preview' && (
                  <button className="secondary small" onClick={() => navigate(`/c/${course.id}/preview`)}>Preview</button>
                )}
                {step === 'share' && !done && <button className="link small" onClick={markShared}>Mark as shared</button>}
              </div>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
