import { useEffect, useState } from 'react'

export function Banner({ kind = 'info', children, action }) {
  return (
    <div className={`banner ${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      <div className="banner-body">{children}</div>
      {action}
    </div>
  )
}

export function ErrorText({ error }) {
  if (!error) return null
  return <p className="error" role="alert">{typeof error === 'string' ? error : error.message}</p>
}

export function Badge({ tone = 'neutral', children }) {
  return <span className={`badge ${tone}`}>{children}</span>
}

export function Meter({ percent, label }) {
  const p = Math.max(0, Math.min(100, percent || 0))
  return (
    <div className="meter" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={p} aria-label={label}>
      <div className={`meter-fill ${p >= 100 ? 'full' : p >= 80 ? 'high' : ''}`} style={{ width: `${p}%` }} />
    </div>
  )
}

export function CopyCode({ code, onCopied }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try { await navigator.clipboard.writeText(code) } catch { /* clipboard blocked: the code is still visible */ }
    setCopied(true)
    onCopied?.()
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <span className="copycode">
      <code>{code}</code>
      <button type="button" className="secondary small" onClick={copy}>{copied ? 'Copied' : 'Copy'}</button>
    </span>
  )
}

export function Modal({ title, onClose, children }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title} onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>{title}</h2>
          <button className="link" onClick={onClose} aria-label="Close">✕</button>
        </div>
        {children}
      </div>
    </div>
  )
}

export function Loading({ text = 'Loading…' }) {
  return <p className="center-note">{text}</p>
}

// Runs an async action, tracking busy and error state for the control that triggered it.
export function useAction() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const run = async (fn) => {
    setBusy(true)
    setError(null)
    try {
      return await fn()
    } catch (e) {
      setError(e)
      return undefined
    } finally {
      setBusy(false)
    }
  }
  return { busy, error, run, setError }
}
