import { useState } from 'react'
import { api } from '../api.js'
import { day, money, tokens } from '../format.js'
import { ErrorText, Meter, useAction } from '../ui.jsx'

export default function Plan({ course, reload, cfg }) {
  const { plan } = course
  const [cap, setCap] = useState(plan.token_cap)
  const [period, setPeriod] = useState(plan.cap_period)
  const [saved, setSaved] = useState(false)
  const { busy, error, run } = useAction()
  const presets = cfg.plans.cap_presets[period]
  const options = presets.includes(cap) ? presets : [...presets, cap].sort((a, b) => a - b)

  const save = () => run(async () => {
    await api.updateCourse(course.id, { token_cap: cap, cap_period: period })
    setSaved(true)
    await reload()
  })
  return (
    <div>
      <h2>Plan and limits</h2>
      {course.billing && (
        <div className="card">
          <h3>Billing</h3>
          <p>
            {course.billing.price_cents ? <>Paid {money(course.billing.price_cents)}{course.billing.paid_at ? ` on ${day(course.billing.paid_at)}` : ''} for one term.</>
              : 'Demo course: no payment.'}
          </p>
          <p className="muted small">Payments run in {course.billing.mode === 'stripe' ? 'Stripe test mode' : 'the built-in test checkout'}. Refunds, plan changes and invoices aren’t available in this version.</p>
        </div>
      )}
      <div className="card">
        <h3>Seats</h3>
        <p>{course.seats_used.students} of {plan.student_seats} student seats used · {course.seats_used.staff} of {plan.staff_seats} staff accounts</p>
        <h3>Course AI budget this term</h3>
        <p>{tokens(course.tokens_used)} of {tokens(plan.token_ceiling)} tokens used, including staff previews.</p>
        <Meter percent={(100 * course.tokens_used) / Math.max(1, plan.token_ceiling)} label="Course tokens used" />
      </div>
      <div className="card form-grid">
        <h3 className="span2">Allowance per student</h3>
        <label htmlFor="pperiod">Resets every</label>
        <select id="pperiod" value={period} onChange={(e) => { setPeriod(e.target.value); setCap(cfg.plans.cap_presets[e.target.value][1] || cfg.plans.cap_presets[e.target.value][0]); setSaved(false) }}>
          <option value="day">day</option><option value="week">week</option><option value="term">term (no reset)</option>
        </select>
        <label htmlFor="pcap">Tokens per student</label>
        <div>
          <select id="pcap" value={cap} onChange={(e) => { setCap(Number(e.target.value)); setSaved(false) }}>
            {options.map((v) => <option key={v} value={v}>{tokens(v)} per {period}</option>)}
          </select>
          <p className="muted small">≈ {Math.floor(cap / cfg.plans.tokens_per_question)} questions per {period}. The course budget above stays the same.</p>
        </div>
        <span />
        <div>
          <ErrorText error={error} />
          <button className="primary" disabled={busy} onClick={save}>Save allowance</button>
          {saved && <span className="muted"> Saved.</span>}
        </div>
      </div>
    </div>
  )
}
