import { useState } from 'react'
import { useAccessibility } from './accessibility.jsx'
import { canResetPassword, sendPasswordReset, signIn, signInWithGoogle, signUp, updatePassword } from './auth.js'
import { Banner, ErrorText, useAction } from './ui.jsx'

// Log in, create an account, forgot password, and set a new password (after the emailed reset link).
export default function AuthScreen({ cfg, notice, initialMode = 'login', onSignedIn, onDone }) {
  const [mode, setMode] = useState(initialMode)
  const [form, setForm] = useState({ name: '', email: '', password: '', confirm: '', account_type: 'student' })
  const [info, setInfo] = useState('')
  const { busy, error, run, setError } = useAction()
  const { openA11yModal, activeBadgeCount } = useAccessibility()
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const setRole = (role) => setForm((prev) => ({ ...prev, account_type: role }))
  const go = (m) => { setMode(m); setError(null); setInfo('') }
  const google = cfg.auth.google

  const submit = (e) => {
    e.preventDefault()
    run(async () => {
      if (mode === 'login') {
        await signIn(form)
        await onSignedIn()
      } else if (mode === 'signup') {
        const r = await signUp(form)
        if (r?.needsConfirm) {
          setInfo('Check your email for a confirmation link, then log in.')
          setMode('login')
        } else {
          await onSignedIn()
        }
      } else if (mode === 'forgot') {
        await sendPasswordReset(form.email)
        setInfo('If an account exists for that email, a reset link is on its way.')
      } else if (mode === 'reset') {
        if (form.password !== form.confirm) throw new Error('The passwords don’t match.')
        await updatePassword(form.password)
        onDone()
      }
    })
  }

  const titles = { login: 'Log in', signup: 'Create your account', forgot: 'Reset your password', reset: 'Set a new password' }
  return (
    <main className="signin">
      <div className="signin-top-a11y">
        <button type="button" className="canvas-a11y-pill" onClick={openA11yModal}>
          Appearance & Accessibility{activeBadgeCount > 0 ? ` (${activeBadgeCount})` : ''}
        </button>
      </div>
      <form onSubmit={submit} className="card signin-ucla-card" noValidate>
        <div className="signin-ucla-banner">
          <span className="ucla-signin-logo">UCLA</span>
          <span className="ucla-signin-pill">BRUIN LEARN · AI STUDIO</span>
        </div>
        <h1>BruinBuddy</h1>
        <p className="muted">An AI tutor & visual concept studio that teaches from your course’s own materials.</p>
        {notice && <Banner kind="warning">{notice}</Banner>}
        {info && <Banner>{info}</Banner>}
        <h2 className="formtitle">{titles[mode]}</h2>

        {google && (mode === 'login' || mode === 'signup') && (
          <>
            <button type="button" className="secondary" onClick={() => run(signInWithGoogle)} disabled={busy}>
              Continue with Google
            </button>
            <div className="divider"><span>or</span></div>
          </>
        )}

        {mode === 'signup' && (
          <>
            <label>I am signing up as</label>
            <div className="role-selector-grid" role="radiogroup" aria-label="Account role">
              <button
                type="button"
                role="radio"
                aria-checked={form.account_type === 'student'}
                className={`role-option-card ${form.account_type === 'student' ? 'active' : ''}`}
                onClick={() => setRole('student')}
              >
                <span className="role-option-title">I am a Student</span>
                <span className="role-option-desc">
                  Join a course with your class code, ask the AI Tutor, and generate concept animations.
                </span>
              </button>
              <button
                type="button"
                role="radio"
                aria-checked={form.account_type === 'instructor'}
                className={`role-option-card ${form.account_type === 'instructor' ? 'active' : ''}`}
                onClick={() => setRole('instructor')}
              >
                <span className="role-option-title">I am an Instructor / Tutor</span>
                <span className="role-option-desc">
                  Create and manage courses, upload materials, set problem modes, and view analytics.
                </span>
              </button>
            </div>

            <label htmlFor="name">Your name</label>
            <input id="name" value={form.name} onChange={set('name')} autoComplete="name" maxLength={60} required />
          </>
        )}
        {mode !== 'reset' && (
          <>
            <label htmlFor="email">Email</label>
            <input id="email" type="email" value={form.email} onChange={set('email')} autoComplete="email" required autoFocus />
          </>
        )}
        {mode !== 'forgot' && (
          <>
            <label htmlFor="password">{mode === 'reset' ? 'New password' : 'Password'}</label>
            <input id="password" type="password" value={form.password} onChange={set('password')} minLength={8} required
                   autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
            {mode !== 'login' && <p className="muted small">At least 8 characters.</p>}
          </>
        )}
        {mode === 'reset' && (
          <>
            <label htmlFor="confirm">Confirm new password</label>
            <input id="confirm" type="password" value={form.confirm} onChange={set('confirm')} autoComplete="new-password" />
          </>
        )}
        <ErrorText error={error} />
        <button className="primary" type="submit" disabled={busy}>
          {busy ? 'Please wait…' : { login: 'Log in', signup: 'Create account', forgot: 'Send reset link', reset: 'Save password' }[mode]}
        </button>

        <p className="small authlinks">
          {mode === 'login' && (
            <>
              {canResetPassword() && <button type="button" className="link" onClick={() => go('forgot')}>Forgot password?</button>}
              <button type="button" className="link" onClick={() => go('signup')}>Create an account</button>
            </>
          )}
          {(mode === 'signup' || mode === 'forgot') && (
            <button type="button" className="link" onClick={() => go('login')}>I already have an account</button>
          )}
        </p>
        {cfg.auth.provider === 'local' && (
          <p className="muted small">Development sign-in: accounts are stored on this server. Production uses Supabase Auth.</p>
        )}
        <p className="muted small"><a href="#/about">About BruinBuddy</a></p>
      </form>
    </main>
  )
}
