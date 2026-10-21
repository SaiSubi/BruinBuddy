import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { day, tokens } from '../format.js'
import { Badge, ErrorText, Loading, Meter } from '../ui.jsx'

const RANGES = [['7d', '7 days'], ['30d', '30 days'], ['term', 'Whole term']]

function Hidden({ panel }) {
  return <p className="muted small">{panel.reason}</p>
}

function DayChart({ series }) {
  const max = Math.max(1, ...series.map((d) => d.count))
  const every = Math.ceil(series.length / 8)
  return (
    <div className="daychart" role="img" aria-label={`Questions per day, peak ${max}`}>
      {series.map((d, i) => (
        <div key={d.date} className="daycol" title={`${d.date}: ${d.count} questions`}>
          <div className="daybar" style={{ height: `${(d.count / max) * 100}%` }} />
          <span className="daylabel">{i % every === 0 ? d.date.slice(5) : ''}</span>
        </div>
      ))}
    </div>
  )
}

export default function Dashboard({ course }) {
  const [range, setRange] = useState('7d')
  const [d, setD] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    setD(null)
    api.dashboard(course.id, range).then(setD).catch(setError)
  }, [course.id, range])

  return (
    <div className="dashboard">
      <div className="row-between">
        <h2>Dashboard {d?.sample_data && <Badge tone="warn">Includes sample data</Badge>}</h2>
        <div className="segmented" role="group" aria-label="Time range">
          {RANGES.map(([k, l]) => (
            <button key={k} className={range === k ? 'active' : ''} aria-pressed={range === k} onClick={() => setRange(k)}>{l}</button>
          ))}
        </div>
      </div>
      <p className="muted small">Aggregates only. Preview chats are excluded, and breakdowns stay hidden until at least 5 students are active.</p>
      <ErrorText error={error} />
      {!d ? <Loading /> : (
        <>
          <div className="tiles">
            <div className="tile"><span className="tile-num">{d.overview.active_students}</span><span className="muted small">active students</span></div>
            <div className="tile"><span className="tile-num">{d.overview.questions}</span><span className="muted small">questions</span></div>
            <div className="tile"><span className="tile-num">{d.overview.seats_used}/{d.overview.student_seats}</span><span className="muted small">seats used</span></div>
            <div className="tile">
              <span className="tile-num">{tokens(d.overview.tokens_used)}</span>
              <span className="muted small">of {tokens(d.overview.token_ceiling)} tokens this term</span>
              <Meter percent={(100 * d.overview.tokens_used) / Math.max(1, d.overview.token_ceiling)} label="Course tokens used" />
            </div>
          </div>
          <div className="card">
            <h3>Questions per day</h3>
            <DayChart series={d.overview.questions_per_day} />
          </div>
          <div className="cards two">
            <div className="card">
              <h3>Most-asked materials</h3>
              {d.materials.hidden ? <Hidden panel={d.materials} /> : !d.materials.items.length ? <p className="muted small">No cited answers yet.</p> : (
                <ol className="barlist">
                  {d.materials.items.map((m) => (
                    <li key={m.doc_id}>
                      <span>{m.title} <span className="muted small">{m.kind}</span></span>
                      <span className="num">{m.questions}</span>
                    </li>
                  ))}
                </ol>
              )}
            </div>
            <div className="card">
              <h3>Where students are stuck</h3>
              {d.stuck.hidden ? <Hidden panel={d.stuck} /> : !d.stuck.items.length ? (
                <p className="muted small">No problem set has questions from 5 or more students yet.</p>
              ) : (
                <table className="table compact">
                  <thead><tr><th>Problem set</th><th className="num">Students</th><th className="num">Q / student</th><th className="num" title="Answer checker results">✓ / ◐ / ✗</th></tr></thead>
                  <tbody>
                    {d.stuck.items.map((r) => (
                      <tr key={r.doc_id}>
                        <td>{r.title}</td><td className="num">{r.students}</td><td className="num">{r.questions_per_student}</td>
                        <td className="num">{r.correct} / {r.partial} / {r.incorrect}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {!d.stuck.hidden && d.stuck.hidden_sets > 0 && <p className="muted small">{d.stuck.hidden_sets} set(s) hidden: fewer than 5 students.</p>}
            </div>
          </div>
          <div className="card">
            <h3>Unanswered questions</h3>
            <p className="muted small">Questions the course materials didn’t cover. No names; email addresses are masked.</p>
            {d.unanswered.hidden ? <Hidden panel={d.unanswered} /> : !d.unanswered.items.length ? <p className="muted small">None in this period.</p> : (
              <ul className="plain unanswered">
                {d.unanswered.items.map((u, i) => <li key={i}><span>“{u.text}”</span><span className="muted small">{day(u.at)}</span></li>)}
              </ul>
            )}
          </div>
          <div className="card">
            <h3>Student usage</h3>
            {!d.students.length ? <p className="muted small">No student activity in this period.</p> : (
              <div className="tablewrap">
                <table className="table compact">
                  <thead><tr><th>Student</th><th className="num">Questions</th><th className="num">Tokens</th></tr></thead>
                  <tbody>{d.students.map((s) => <tr key={s.user_id}><td>{s.name}</td><td className="num">{s.questions}</td><td className="num">{tokens(s.tokens)}</td></tr>)}</tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
