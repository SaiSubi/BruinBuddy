export const money = (cents) => `$${(cents / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

export const tokens = (n) => (n >= 1_000_000 ? `${+(n / 1_000_000).toFixed(1)}M` : n >= 1000 ? `${Math.round(n / 1000)}k` : `${n}`)

export const when = (ts) => (ts ? new Date(ts * 1000).toLocaleString(undefined, {
  weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
}) : '')

export const day = (ts) => (ts ? new Date(ts * 1000).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : '')

// <input type="datetime-local"> works in local time without a zone
export const toLocalInput = (ts) => {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}
export const fromLocalInput = (v) => (v ? new Date(v).getTime() / 1000 : null)

export const PERIOD = { day: 'day', week: 'week', term: 'term' }
export const ROLE = { owner: 'Owner', staff: 'Staff', student: 'Student' }
