import { useEffect, useRef, useState } from 'react'
import { api, sendMessage, fileUrl } from './api.js'
import Message from './Message.jsx'

const SUGGESTIONS = [
  'Explain Bayes’ theorem and why we need a prior.',
  'What should I review for an exam on conditional probability?',
  'I’m stuck on a problem. Can you help me think through it?',
]

export default function Chat({ user, onSignOut, onAbout }) {
  const [chats, setChats] = useState([])
  const [chatId, setChatId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [source, setSource] = useState(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const bottom = useRef(null)

  const loadChats = () => api.chats().then(setChats)
  useEffect(() => { loadChats() }, [])
  useEffect(() => { bottom.current?.scrollIntoView({ block: 'end' }) }, [messages])

  const open = async (id) => {
    setChatId(id); setSource(null); setMenuOpen(false)
    const c = await api.chat(id)
    setMessages(c.messages)
  }
  const newChat = async () => {
    if (chatId && messages.length === 0) { setMenuOpen(false); return chatId } // already on an empty chat
    const c = await api.newChat()
    setChatId(c.id); setMessages([]); setSource(null); setMenuOpen(false)
    loadChats()
    return c.id
  }

  const ask = async (text, existingId) => {
    text = text.trim()
    if (!text || busy) return
    let id = existingId ?? chatId
    if (!id) id = await newChat()
    setInput('')
    setBusy(true)
    const retry = () => {
      setMessages((ms) => ms.slice(0, -2))
      ask(text, id)
    }
    setMessages((ms) => [...ms, { role: 'user', content: text }, { role: 'assistant', content: '', citations: [] }])
    const patchLast = (fn) => setMessages((ms) => ms.map((m, i) => (i === ms.length - 1 ? fn(m) : m)))
    try {
      await sendMessage(id, text, (ev) => {
        if (ev.type === 'delta') patchLast((m) => ({ ...m, content: m.content + ev.text }))
        else if (ev.type === 'replace') patchLast((m) => ({ ...m, content: ev.text }))
        else if (ev.type === 'done') patchLast(() => ev.message)
        else if (ev.type === 'error') patchLast((m) => ({ ...m, error: ev.message, onRetry: retry }))
      })
    } catch (err) {
      patchLast((m) => ({ ...m, error: err.message && err.message !== 'Request failed' ? err.message : 'Something went wrong. Try again.', onRetry: retry }))
    } finally {
      setBusy(false)
      loadChats()
    }
  }

  const onKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(input) }
  }

  return (
    <div className="app">
      <aside className={`sidebar ${menuOpen ? 'open' : ''}`}>
        <button className="primary" onClick={newChat}>+ New chat</button>
        <nav aria-label="Chats" className="chatlist">
          {chats.map((c) => (
            <button key={c.id} className={`chatitem ${c.id === chatId ? 'active' : ''}`} onClick={() => open(c.id)}>
              {c.title}
            </button>
          ))}
        </nav>
        <div className="sidefoot">
          <span>{user.name}</span>
          <button className="link" onClick={onAbout}>About</button>
          <button className="link" onClick={onSignOut}>Sign out</button>
        </div>
      </aside>

      <main className="main">
        <header className="topbar mobile-only">
          <button className="link" onClick={() => setMenuOpen((v) => !v)} aria-label="Toggle chat list">☰ Chats</button>
        </header>
        <div className="scroll" role="log" aria-live="polite" aria-label="Conversation">
          {messages.length === 0 ? (
            <div className="welcome">
              <h1>What are you studying?</h1>
              <p className="muted">Ask about 18.05 topics. I answer from the course notes and readings, and I’ll guide you instead of handing over answers to assigned problems.</p>
              <div className="suggest">
                {SUGGESTIONS.map((s) => (
                  <button key={s} className="suggestion" onClick={() => ask(s)}>{s}</button>
                ))}
              </div>
            </div>
          ) : (
            <div className="thread">
              {messages.map((m, i) => (
                <Message key={m.id ?? `t${i}`} m={m} onCite={setSource} />
              ))}
              {busy && <p className="muted small" aria-hidden="true">BruinBuddy is thinking…</p>}
              <div ref={bottom} />
            </div>
          )}
        </div>
        <form className="composer" onSubmit={(e) => { e.preventDefault(); ask(input) }}>
          <textarea
            aria-label="Ask a question"
            placeholder="Ask a question…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKey}
            rows={2}
          />
          <button className="primary" type="submit" disabled={busy || !input.trim()}>Send</button>
        </form>
      </main>

      <aside className={`sourcepane ${source ? 'open' : ''}`} aria-label="Source">
        {source ? (
          <>
            <div className="srchead">
              <strong>Source {source.n}</strong>
              <button className="link" onClick={() => setSource(null)} aria-label="Close source">✕</button>
            </div>
            <p className="srctitle">{source.title}</p>
            <p className="muted small">Page {source.page}</p>
            <pre className="srctext">{source.text}</pre>
            <a className="primary linkbtn" href={fileUrl(source.url)} target="_blank" rel="noreferrer">Open document</a>
          </>
        ) : (
          <p className="muted small">Click a numbered citation to see the passage it came from.</p>
        )}
      </aside>
    </div>
  )
}
