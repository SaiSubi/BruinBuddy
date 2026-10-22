import { useEffect, useRef, useState } from 'react'
import { api } from './api.js'
import { RailIcon } from './CanvasShell.jsx'
import { PauseBanner } from './CourseHome.jsx'
import Message, { Markdown } from './Message.jsx'
import { navigate } from './router.js'
import { Badge, Banner, ErrorText, Loading, Meter, Modal, useAction } from './ui.jsx'

// AI-assisted checkpoint assignments for students (and staff previewing them). The server sends only what a student
// may see: prompts of open checkpoints and results of passed or skipped ones, never target answers or rubrics.

const STATUS = {
  passed: ['Passed', 'good'], active: ['Active', 'info'], skipped: ['Skipped', 'warn'], locked: ['Locked', 'neutral'],
}
const HINT_TEXT = 'I’m stuck on this checkpoint. Could I have a hint?'

function StepIcon({ status, n }) {
  if (status === 'passed') {
    return (
      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.4" aria-hidden="true">
        <polyline points="5 12.5 10 17 19 7" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    )
  }
  if (status === 'skipped') {
    return (
      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true">
        <polyline points="6 6 12 12 6 18" strokeLinecap="round" strokeLinejoin="round" />
        <line x1="16" y1="6" x2="16" y2="18" strokeLinecap="round" />
      </svg>
    )
  }
  if (status === 'locked') {
    return (
      <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <rect x="5" y="11" width="14" height="9" rx="2" />
        <path d="M8 11V8a4 4 0 0 1 8 0v3" />
      </svg>
    )
  }
  return <span aria-hidden="true">{n}</span>
}

export function Stepper({ checkpoints }) {
  return (
    <ol className="ga-stepper" aria-label="Checkpoint progress">
      {checkpoints.map((cp) => {
        const [label, tone] = STATUS[cp.status] || STATUS.locked
        return (
          <li key={cp.index} className={`ga-step ${cp.status}`} aria-current={cp.status === 'active' ? 'step' : undefined}>
            <span className="ga-step-dot"><StepIcon status={cp.status} n={cp.index + 1} /></span>
            <div className="ga-step-body">
              <div className="ga-step-head">
                <strong>{cp.title}</strong>
                <Badge tone={tone}>{label}</Badge>
              </div>
              <div className="muted small">
                {cp.status === 'passed' || cp.status === 'skipped' ? `${cp.earned_points} / ${cp.points} pts` : `${cp.points} pts`}
              </div>
              {cp.status === 'active' && cp.prompt && <div className="ga-step-prompt"><Markdown text={cp.prompt} /></div>}
              {cp.result && (
                <div className="ga-step-result">
                  <span className="muted small">Result</span>
                  <Markdown text={cp.result} />
                </div>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}

export function AssignmentList({ course, compact = false }) {
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    api.assignments(course.id).then(setItems).catch((e) => { setError(e); setItems([]) })
  }, [course.id])
  if (!items) return <Loading />
  if (compact && !items.length) return null
  return (
    <div className="canvas-group-box">
      <div className="canvas-group-header">
        <span>AI-Guided Assignments</span>
        <span className="muted small">{items.length} assignment(s)</span>
      </div>
      <ErrorText error={error} />
      <div className="canvas-group-rows">
        {items.length ? items.map((a) => {
          const sub = a.submission
          const total = a.total_points || 0
          const score = sub?.score || 0
          const done = (a.checkpoints || []).filter((c) => c.status === 'passed' || c.status === 'skipped').length
          const percent = a.checkpoint_count ? Math.round((100 * (sub?.status === 'completed' ? a.checkpoint_count : done)) / a.checkpoint_count) : 0
          return (
            <div key={a.id} className="canvas-item-row">
              <span className="canvas-item-icon" aria-hidden="true"><RailIcon name="assignment" size={18} /></span>
              <div className="canvas-item-main">
                <a className="canvas-chat-link" href={`#/c/${course.id}/assignments/${a.id}`}>{a.title}</a>
                <div className="muted small">
                  {a.checkpoint_count} checkpoints · {sub ? `${score} / ${total} pts` : `${total} pts`}
                </div>
                {sub && <div className="ga-list-meter"><Meter percent={percent} label={`${a.title} progress`} /></div>}
              </div>
              <div className="canvas-item-actions">
                {sub?.status === 'completed' ? <Badge tone="good">Completed</Badge> : sub ? <Badge tone="info">In progress</Badge> : <Badge>Not started</Badge>}
                <a className="primary small btnlink" href={`#/c/${course.id}/assignments/${a.id}`}>
                  {sub?.status === 'completed' ? 'Review' : sub ? 'Continue' : 'Start'}
                </a>
              </div>
            </div>
          )
        }) : (
          <div className="canvas-item-empty muted small">Your instructor hasn’t published any AI-guided assignments yet.</div>
        )}
      </div>
    </div>
  )
}

function Workspace({ course, assignmentId, preview }) {
  const [data, setData] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [input, setInput] = useState('')
  const [confirmSkip, setConfirmSkip] = useState(false)
  const { busy, error, run, setError } = useAction()
  const bottom = useRef(null)

  useEffect(() => {
    api.assignment(assignmentId).then(setData).catch(setLoadError)
  }, [assignmentId])
  useEffect(() => { bottom.current?.scrollIntoView({ block: 'end' }) }, [data?.messages?.length, busy])

  if (loadError) {
    return (
      <div className="narrow">
        <Banner kind="error">{loadError.status === 404 ? 'This assignment doesn’t exist or isn’t available to you.' : loadError.message}</Banner>
        <a className="secondary btnlink" href={`#/c/${course.id}/assignments`}>Back to assignments</a>
      </div>
    )
  }
  if (!data) return <Loading />

  const { assignment: a, submission: sub, messages } = data
  const active = a.checkpoints.find((c) => c.status === 'active')
  const completed = sub.status === 'completed'
  const paused = Boolean(course.pause?.active)

  const send = (content, hint = false) => run(async () => {
    const r = await api.assignmentTurn(a.id, content, hint)
    setData((d) => ({ ...d, assignment: r.assignment, submission: r.submission,
                      messages: [...d.messages, r.user_message, r.message] }))
    if (!hint) setInput('')
  })
  const skip = () => run(async () => {
    setConfirmSkip(false)
    const r = await api.skipCheckpoint(a.id)
    setData((d) => ({ ...d, assignment: r.assignment, submission: r.submission, messages: [...d.messages, r.message] }))
  })
  const onKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (input.trim() && !busy) send(input.trim())
    }
  }

  return (
    <div className="ga-workspace">
      <div className="ga-head">
        <div>
          <a className="link small" href={`#/c/${course.id}/assignments`}>← All assignments</a>
          <h1 className="ga-title">{a.title} {preview && <Badge>Preview</Badge>}</h1>
          <p className="muted small">Your instructor can see this assignment’s conversation and your score.</p>
        </div>
        <div className="ga-score" aria-label="Score">
          <span className="ga-score-num">{sub.score}</span>
          <span className="muted"> / {a.total_points} pts</span>
        </div>
      </div>
      <PauseBanner pause={course.pause} />
      {completed && <Banner kind="info">Assignment complete: {sub.score} of {a.total_points} points. You can review the conversation below.</Banner>}

      <div className="ga-grid">
        <aside className="ga-left card" aria-label="Problem and checkpoints">
          <h2 className="ga-section">Problem</h2>
          <div className="ga-problem"><Markdown text={a.problem_statement} /></div>
          <h2 className="ga-section">Checkpoints</h2>
          <Stepper checkpoints={a.checkpoints} />
        </aside>

        <section className="ga-chat card" aria-label="Socratic walkthrough">
          {active && (
            <div className="ga-active">
              <span className="muted small">Working on</span>
              <strong> {active.title}</strong>
              <span className="muted small"> · {active.points} pts</span>
            </div>
          )}
          <div className="ga-thread" role="log" aria-live="polite" aria-label="Conversation">
            {messages.map((m) => <Message key={m.id} m={{ ...m, citations: [] }} onCite={() => {}} />)}
            {busy && <p className="muted small" aria-hidden="true">BruinBuddy is checking your work…</p>}
            <div ref={bottom} />
          </div>
          <ErrorText error={error} />
          {!completed && (
            <>
              <div className="ga-actions">
                <button type="button" className="secondary small" disabled={busy || paused} onClick={() => send(HINT_TEXT, true)}>
                  Request hint
                </button>
                <button type="button" className="secondary small" disabled={busy || paused} onClick={() => { setError(null); setConfirmSkip(true) }}>
                  Skip &amp; reveal step (0 pts)
                </button>
              </div>
              <form className="composer ga-composer" onSubmit={(e) => { e.preventDefault(); if (input.trim()) send(input.trim()) }}>
                <textarea
                  aria-label="Your answer or question"
                  placeholder={paused ? 'The tutor is paused' : 'Explain your reasoning for this checkpoint…'}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={onKey}
                  rows={2}
                  maxLength={4000}
                />
                <button className="primary" type="submit" disabled={busy || !input.trim()}>Send</button>
              </form>
            </>
          )}
        </section>
      </div>

      {confirmSkip && active && (
        <Modal title="Skip this checkpoint?" onClose={() => setConfirmSkip(false)}>
          <p>You’ll get <strong>0 of {active.points} points</strong> for {active.title}. Its result will be shown so you can
            continue with the next step. This can’t be undone.</p>
          <div className="inline">
            <button className="primary" disabled={busy} onClick={skip}>Skip and reveal</button>
            <button className="secondary" onClick={() => setConfirmSkip(false)}>Keep trying</button>
          </div>
        </Modal>
      )}
    </div>
  )
}

export default function GuidedAssignments({ course, assignmentId, preview }) {
  if (assignmentId) return <Workspace key={assignmentId} course={course} assignmentId={assignmentId} preview={preview} />
  return (
    <div className="ga-index">
      {preview && (
        <Banner action={<button className="secondary small" onClick={() => navigate(`/c/${course.id}/staff/assignments`)}>Manage assignments</button>}>
          Preview: this is the student view. Your own attempts are labelled as previews and left out of the gradebook.
        </Banner>
      )}
      <h1 className="ucla-section-heading">AI-Guided Assignments</h1>
      <p className="muted">
        Work through one problem a checkpoint at a time. The tutor asks guiding questions instead of giving answers;
        each checkpoint you reach earns its points. Stuck? Ask for a hint, or skip a step for 0 points to see its result.
      </p>
      <AssignmentList course={course} />
    </div>
  )
}
