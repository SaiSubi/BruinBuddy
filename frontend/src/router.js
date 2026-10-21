// Tiny hash router: #/c/12/chat/40 -> ['c', '12', 'chat', '40']. Works on Vercel and when the backend serves the build.
import { useEffect, useState } from 'react'

const parse = () => window.location.hash.replace(/^#\/?/, '').split('?')[0].split('/').filter(Boolean)

export function useRoute() {
  const [parts, setParts] = useState(parse)
  useEffect(() => {
    const on = () => setParts(parse())
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return parts
}

export function navigate(path) {
  const target = '#' + (path.startsWith('/') ? path : '/' + path)
  if (window.location.hash !== target) window.location.hash = target
}

// BruinBuddy's one-time query parameters (?checkout=…, ?reset=1, a sign-in error) are read once and removed from the
// address bar. Supabase's own ?code= is left alone: supabase-js reads it when the client starts, then removes it.
const OWN_PARAMS = ['checkout', 'course', 'session_id', 'reset', 'error', 'error_code', 'error_description']

export function takeQueryParams() {
  const url = new URL(window.location.href)
  const params = {}
  for (const key of OWN_PARAMS) {
    if (url.searchParams.has(key)) {
      params[key] = url.searchParams.get(key)
      url.searchParams.delete(key)
    }
  }
  if (Object.keys(params).length) window.history.replaceState(window.history.state, '', url.toString())
  return params
}
