import { useEffect, useState } from 'react'
import { api, fileUrl } from './api.js'
import { money, tokens } from './format.js'
import { Banner, ErrorText, useAction } from './ui.jsx'

// Sends the browser to Stripe Checkout (or, without Stripe keys, the server's test checkout page).
export async function startCheckout(courseId) {
  const { url } = await api.checkout(courseId)
  window.location.href = fileUrl(url)
}

export function TestModeNote({ cfg }) {
  return cfg.billing.mode === 'stripe' ? (
    <p className="muted small">Stripe test mode: pay with card 4242 4242 4242 4242, any future date and any CVC. No real charge.</p>
  ) : (
    <p className="muted small">This server has no Stripe keys yet, so checkout uses a built-in test page. No card is charged.</p>
  )
}

export default function CreateCourse({ cfg }) {
  const presets = cfg.plans.cap_presets
  const [plan, setPlan] = useState({ name: '', student_seats: 40, staff_seats: 2, cap_period: 'week', token_cap: 100_000 })
  const [quote, setQuote] = useState(null)
  const [quoteError, setQuoteError] = useState(null)
  const { busy, error, run } = useAction()

  useEffect(() => {
    const t = setTimeout(() => {
      const { name, ...p } = plan
      api.quote(p).then((q) => { setQuote(q); setQuoteError(null) }).catch((e) => { setQuote(null); setQuoteError(e) })
    }, 250)
    return () => clearTimeout(t)
  }, [plan])

  const num = (k) => (e) => setPlan({ ...plan, [k]: Math.max(0, parseInt(e.target.value || '0', 10)) })
  const setPeriod = (e) => {
    const period = e.target.value
    const options = presets[period]
    setPlan({ ...plan, cap_period: period, token_cap: options[Math.min(1, options.length - 1)] })
  }

  const submit = (e) => {
    e.preventDefault()
    run(async () => {
      const course = await api.createCourse({ ...plan, name: plan.name.trim() })
      await startCheckout(course.id)
    })
  }

  return (
    <form className="narrow" onSubmit={submit}>
      <h1>Create a course</h1>
      <p className="muted">You pay once per course for a 10-week term. Students join free with a code.</p>
      <div className="card form-grid">
        <label htmlFor="cname">Course name</label>
        <input id="cname" value={plan.name} onChange={(e) => setPlan({ ...plan, name: e.target.value })}
               placeholder="Stats 100A, Fall 2026" maxLength={120} required />
        <label htmlFor="seats">Student seats</label>
        <input id="seats" type="number" min={1} max={2000} value={plan.student_seats} onChange={num('student_seats')} />
        <label htmlFor="staff">Staff accounts (TAs, co-instructors)</label>
        <input id="staff" type="number" min={0} max={50} value={plan.staff_seats} onChange={num('staff_seats')} />
        <label htmlFor="period">Allowance resets every</label>
        <select id="period" value={plan.cap_period} onChange={setPeriod}>
          <option value="day">day</option>
          <option value="week">week</option>
          <option value="term">term (no reset)</option>
        </select>
        <label htmlFor="cap">Allowance per student</label>
        <div>
          <select id="cap" value={plan.token_cap} onChange={(e) => setPlan({ ...plan, token_cap: Number(e.target.value) })}>
            {presets[plan.cap_period].map((v) => (
              <option key={v} value={v}>{tokens(v)} tokens per {plan.cap_period}</option>
            ))}
          </select>
          <p className="muted small">≈ {Math.floor(plan.token_cap / cfg.plans.tokens_per_question)} questions per {plan.cap_period}</p>
        </div>
      </div>

      <div className="card">
        <h2>Price for the term</h2>
        {quoteError && <ErrorText error={quoteError} />}
        {quote && (
          <table className="pricing">
            <tbody>
              {quote.lines.filter((l) => l.cents > 0).map((l) => (
                <tr key={l.label}><td>{l.label}</td><td className="num">{money(l.cents)}</td></tr>
              ))}
              <tr className="total"><td>Total</td><td className="num">{money(quote.price_cents)}</td></tr>
            </tbody>
          </table>
        )}
        <p className="muted small">The course can use up to {quote ? tokens(quote.token_ceiling) : '…'} tokens this term in total.</p>
        <TestModeNote cfg={cfg} />
        <ErrorText error={error} />
        <button className="primary" type="submit" disabled={busy || !quote || !plan.name.trim()}>
          {busy ? 'Opening checkout…' : `Create course and pay ${quote ? money(quote.price_cents) : ''}`}
        </button>
      </div>
      <Banner>Pricing is a placeholder for the class demo and may change.</Banner>
    </form>
  )
}
