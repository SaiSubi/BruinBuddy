// Sign-up and login. Production uses Supabase Auth in the browser (PKCE); the backend verifies its access token.
// Local development uses the backend's email + password accounts. The provider comes from GET /api/config.
const TOKEN_KEY = 'bb_token'
const API_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '')
let sb = null
let provider = 'local'

const store = {
  get: () => { try { return localStorage.getItem(TOKEN_KEY) } catch { return null } },
  set: (t) => { try { localStorage.setItem(TOKEN_KEY, t) } catch { /* private mode */ } },
  clear: () => { try { localStorage.removeItem(TOKEN_KEY) } catch { /* ignore */ } },
}

export async function initAuth(cfg) {
  provider = cfg?.auth?.provider || 'local'
  if (provider === 'supabase' && cfg.auth.supabase_url && cfg.auth.supabase_anon_key) {
    const { createClient } = await import('@supabase/supabase-js')
    sb = createClient(cfg.auth.supabase_url, cfg.auth.supabase_anon_key, {
      auth: { flowType: 'pkce', detectSessionInUrl: true, persistSession: true, autoRefreshToken: true },
    })
    await sb.auth.getSession() // completes a ?code= redirect (Google, email links) before the app renders
  }
}

export const authProvider = () => provider
export const canResetPassword = () => provider === 'supabase'

export async function getToken() {
  if (sb) {
    const { data } = await sb.auth.getSession()
    return data.session?.access_token || null
  }
  return store.get()
}

async function localAuth(path, body) {
  const r = await fetch(API_BASE + path, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  const data = await r.json().catch(() => ({}))
  if (!r.ok) {
    const d = data.detail
    throw new Error(typeof d === 'string' ? d : Array.isArray(d) ? 'Check the form: ' + (d[0]?.msg || 'invalid input') : 'Could not sign in.')
  }
  store.set(data.token)
  return data
}

export async function signUp({ name, email, password, account_type = 'student' }) {
  if (!sb) return localAuth('/api/auth/signup', { name, email, password, account_type })
  const { data, error } = await sb.auth.signUp({
    email, password, options: { data: { name, account_type }, emailRedirectTo: window.location.origin },
  })
  if (error) throw new Error(error.message)
  return { needsConfirm: !data.session }
}

export async function signIn({ email, password }) {
  if (!sb) return localAuth('/api/auth/login', { email, password })
  const { error } = await sb.auth.signInWithPassword({ email, password })
  if (error) throw new Error(error.message === 'Invalid login credentials' ? 'Wrong email or password.' : error.message)
}

// The role picked before sign-in. Google can't carry it in the account's metadata, so it waits here across the
// redirect and App applies it to a fresh account (see PUT /api/me/account-type).
const ROLE_KEY = 'bb_role'
const PENDING_ROLE_KEY = 'bb_pending_role'
export const lastRole = () => { try { return localStorage.getItem(ROLE_KEY) || '' } catch { return '' } }
export const rememberRole = (role) => { try { localStorage.setItem(ROLE_KEY, role) } catch { /* ignore */ } }
export function takePendingRole() {
  try {
    const role = localStorage.getItem(PENDING_ROLE_KEY)
    localStorage.removeItem(PENDING_ROLE_KEY)
    return role || ''
  } catch { return '' }
}

export async function signInWithGoogle(role) {
  try { localStorage.setItem(PENDING_ROLE_KEY, role) } catch { /* ignore */ }
  const { error } = await sb.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: window.location.origin } })
  if (error) throw new Error(error.message)
}

export async function sendPasswordReset(email) {
  const { error } = await sb.auth.resetPasswordForEmail(email, { redirectTo: window.location.origin + '/?reset=1' })
  if (error) throw new Error(error.message)
}

export async function updatePassword(password) {
  const { error } = await sb.auth.updateUser({ password })
  if (error) throw new Error(error.message)
}

export async function signOut() {
  store.clear()
  if (sb) await sb.auth.signOut().catch(() => {})
}
