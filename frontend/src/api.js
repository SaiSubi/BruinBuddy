// In dev the Vite proxy serves /api; in production VITE_API_BASE points at the Fly backend.
export const API_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '')
const TOKEN_KEY = 'bb_token'

const store = {
  get: () => { try { return localStorage.getItem(TOKEN_KEY) } catch { return null } },
  set: (t) => { try { localStorage.setItem(TOKEN_KEY, t) } catch { /* private mode */ } },
  clear: () => { try { localStorage.removeItem(TOKEN_KEY) } catch { /* ignore */ } },
}

// Citation/file URLs from the server are relative to the backend.
export const fileUrl = (u) => (u && u.startsWith('/') ? API_BASE + u : u)

function headers(extra = {}) {
  const t = store.get()
  return { ...(t ? { Authorization: `Bearer ${t}` } : {}), ...extra }
}

async function json(path, opts = {}) {
  const r = await fetch(API_BASE + path, { ...opts, headers: headers(opts.headers) })
  if (!r.ok) {
    let detail = r.statusText
    try { detail = (await r.json()).detail || detail } catch { /* not json */ }
    const err = new Error(detail)
    err.status = r.status
    throw err
  }
  return r.json()
}

export const api = {
  config: () => json('/api/config'),
  me: () => json('/api/me'),
  signIn: async (name, role, code) => {
    const u = await json('/api/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, role, code }),
    })
    store.set(u.token)
    return u
  },
  signOut: () => { store.clear() },
  hasToken: () => !!store.get(),
  chats: () => json('/api/chats'),
  newChat: () => json('/api/chats', { method: 'POST' }),
  chat: (id) => json(`/api/chats/${id}`),
  dashboard: () => json('/api/dashboard'),
}

// POST a message and read the SSE stream. Calls onEvent for each parsed event.
export async function sendMessage(chatId, content, onEvent) {
  const r = await fetch(`${API_BASE}/api/chats/${chatId}/messages`, {
    method: 'POST',
    headers: headers({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ content }),
  })
  if (!r.ok || !r.body) {
    let detail = 'Request failed'
    try { detail = (await r.json()).detail || detail } catch { /* not json */ }
    throw new Error(detail)
  }
  const reader = r.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    let i
    while ((i = buf.indexOf('\n\n')) >= 0) {
      const line = buf.slice(0, i).trim()
      buf = buf.slice(i + 2)
      if (line.startsWith('data: ')) onEvent(JSON.parse(line.slice(6)))
    }
  }
}
