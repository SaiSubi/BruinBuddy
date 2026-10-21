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

// One-time query parameters (?checkout=…, ?reset=1) are read once and then removed from the address bar.
export function takeQueryParams() {
  const params = Object.fromEntries(new URLSearchParams(window.location.search))
  if (Object.keys(params).length) {
    window.history.replaceState(null, '', window.location.pathname + window.location.hash)
  }
  return params
}
