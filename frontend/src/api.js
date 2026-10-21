// In dev the Vite proxy serves /api; in production VITE_API_BASE points at the Fly backend.
import { getToken } from './auth.js'

export const API_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '')

// File links and the test checkout page come back relative to the backend.
export const fileUrl = (u) => (u && u.startsWith('/') ? API_BASE + u : u)

let onExpired = () => {}
export const setOnExpired = (fn) => { onExpired = fn }

export class ApiError extends Error {
  constructor(status, detail) {
    const message = typeof detail === 'string' ? detail
      : detail?.message || (Array.isArray(detail) ? 'Please check the form and try again.' : 'Something went wrong.')
    super(message)
    this.status = status
    this.until = detail?.until || null
  }
}

async function headers(extra = {}) {
  const t = await getToken()
  return { ...(t ? { Authorization: `Bearer ${t}` } : {}), ...extra }
}

async function request(path, { method = 'GET', body, form } = {}) {
  let r
  try {
    r = await fetch(API_BASE + path, {
      method,
      headers: await headers(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      body: form || (body !== undefined ? JSON.stringify(body) : undefined),
    })
  } catch {
    throw new ApiError(0, 'Can’t reach BruinBuddy. Check your connection and try again.')
  }
  if (!r.ok) {
    let detail = r.statusText
    try { detail = (await r.json()).detail ?? detail } catch { /* not json */ }
    if (r.status === 401) onExpired()
    throw new ApiError(r.status, detail)
  }
  return r.json()
}

const get = (p) => request(p)
const post = (p, body = {}) => request(p, { method: 'POST', body })
const patch = (p, body) => request(p, { method: 'PATCH', body })
const put = (p, body) => request(p, { method: 'PUT', body })
const del = (p) => request(p, { method: 'DELETE' })
const c = (id) => `/api/courses/${id}`

export const api = {
  config: () => get('/api/config'),
  me: () => get('/api/me'),
  quote: (plan) => post('/api/billing/quote', plan),
  createCourse: (body) => post('/api/courses', body),
  checkout: (id) => post(`${c(id)}/checkout`, { return_url: window.location.origin }),
  confirmCheckout: (id, sessionId) => post(`${c(id)}/checkout/confirm`, { session_id: sessionId || '' }),
  join: (code) => post('/api/join', { code }),
  course: (id) => get(c(id)),
  updateCourse: (id, body) => patch(c(id), body),
  rotateCode: (id) => post(`${c(id)}/code/rotate`),
  setupStep: (id, step, done = true) => post(`${c(id)}/setup`, { step, done }),
  materials: (id) => get(`${c(id)}/materials`),
  upload: (id, form) => request(`${c(id)}/materials`, { method: 'POST', form }),
  updateMaterial: (id, doc, body) => patch(`${c(id)}/materials/${doc}`, body),
  replaceFile: (id, doc, form) => request(`${c(id)}/materials/${doc}/file`, { method: 'POST', form }),
  retryMaterial: (id, doc) => post(`${c(id)}/materials/${doc}/retry`),
  deleteMaterial: (id, doc) => del(`${c(id)}/materials/${doc}`),
  guidelines: (id) => get(`${c(id)}/guidelines`),
  saveGuidelines: (id, body) => put(`${c(id)}/guidelines`, body),
  pauses: (id) => get(`${c(id)}/pauses`),
  addPause: (id, body) => post(`${c(id)}/pauses`, body),
  deletePause: (id, pid) => del(`${c(id)}/pauses/${pid}`),
  members: (id) => get(`${c(id)}/members`),
  memberAction: (id, userId, action) => post(`${c(id)}/members/${userId}`, { action }),
  staffCodes: (id) => get(`${c(id)}/staff-codes`),
  createStaffCode: (id) => post(`${c(id)}/staff-codes`),
  revokeStaffCode: (id, codeId) => del(`${c(id)}/staff-codes/${codeId}`),
  dashboard: (id, range) => get(`${c(id)}/dashboard?range=${range}&tz_offset=${new Date().getTimezoneOffset()}`),
  chats: (id) => get(`${c(id)}/chats`),
  newChat: (id, kind = 'chat', docId = null) => post(`${c(id)}/chats`, { kind, doc_id: docId }),
  chat: (chatId) => get(`/api/chats/${chatId}`),
  illustrations: (chatId) => get(`/api/chats/${chatId}/illustrations`),
  illustrate: (chatId, body = {}) => post(`/api/chats/${chatId}/illustrate`, body),
  downloadIllustration: async (illustrationId, format = 'html') => {
    const r = await fetch(`${API_BASE}/api/illustrations/${illustrationId}/download?format=${encodeURIComponent(format)}`, {
      headers: await headers(),
    })
    if (!r.ok) {
      if (r.status === 401) onExpired()
      throw new ApiError(r.status, 'Could not download illustration.')
    }
    return r.blob()
  },
}

// POST a message and read the SSE stream. Calls onEvent for each parsed event.
export async function sendMessage(chatId, content, onEvent) {
  let r
  try {
    r = await fetch(`${API_BASE}/api/chats/${chatId}/messages`, {
      method: 'POST',
      headers: await headers({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ content }),
    })
  } catch {
    throw new ApiError(0, 'Can’t reach BruinBuddy. Check your connection and try again.')
  }
  if (!r.ok || !r.body) {
    let detail = 'Something went wrong. Try again.'
    try { detail = (await r.json()).detail ?? detail } catch { /* not json */ }
    if (r.status === 401) onExpired()
    throw new ApiError(r.status, detail)
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
