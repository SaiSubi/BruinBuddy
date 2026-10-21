import { useEffect, useRef, useState } from 'react'
import { api, fileUrl, sendMessage } from './api.js'
import { when } from './format.js'
import { navigate } from './router.js'
import { Badge, Banner } from './ui.jsx'
import { modeTone, PauseBanner } from './CourseHome.jsx'
import Message from './Message.jsx'

const draftKey = (id) => `bb_draft_${id}`
const loadDraft = (id) => { try { return sessionStorage.getItem(draftKey(id)) || '' } catch { return '' } }
const saveDraft = (id, v) => { try { v ? sessionStorage.setItem(draftKey(id), v) : sessionStorage.removeItem(draftKey(id)) } catch { /* ignore */ } }
const takeFirstMessage = (id) => {
  try {
    const v = sessionStorage.getItem(`bb_first_${id}`)
    sessionStorage.removeItem(`bb_first_${id}`)
    return v
  } catch { return null }
}

const INTRO = {
  pset: 'Paste the problem you’re working on, or tell me where you’re stuck.',
  review: 'Ask for a review plan, or tell me which part of this material is confusing.',
  quiz: 'Ask me to quiz you, and I’ll ask one question at a time.',
  chat: 'Ask about the course. I answer from the course materials, cite them, and guide you instead of handing over answers to graded problems.',
}

export default function ChatView({ course, chatId, preview, onCourseChange }) {
  const [chats, setChats] = useState([])
  const [chat, setChat] = useState(null)
  const [messages, setMessages] = useState([])
  const [rule, setRule] = useState(null)
  const [input, setInput] = useState(() => loadDraft(chatId))
  const [busy, setBusy] = useState(false)
  const [source, setSource] = useState(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const [loadError, setLoadError] = useState(null)
  const [ended, setEnded] = useState('')
  const bottom = useRef(null)
  const startedFirst = useRef(false)
  const home = `#/c/${course.id}${preview ? '/preview' : ''}`

  const loadChats = () => api.chats(course.id).then(setChats).catch(() => {})

  const ask = async (raw) => {
    const text = raw.trim()
    if (!text || busy) return
    setInput('')
    saveDraft(chatId, '')
    setBusy(true)
    const retry = () => {
      setMessages((ms) => ms.slice(0, -2))
      ask(text)
    }
    setMessages((ms) => [...ms, { role: 'user', content: text }, { role: 'assistant', content: '', citations: [] }])
    const patchLast = (fn) => setMessages((ms) => ms.map((m, i) => (i === ms.length - 1 ? fn(m) : m)))
    try {
      await sendMessage(chatId, text, (ev) => {
        if (ev.type === 'delta') patchLast((m) => ({ ...m, content: m.content + ev.text }))
        else if (ev.type === 'replace') patchLast((m) => ({ ...m, content: ev.text }))
        else if (ev.type === 'done') {
          patchLast(() => ev.message)
          if (ev.message.rule) setRule(ev.message.rule)
        } else if (ev.type === 'error') patchLast((m) => ({ ...m, error: ev.message, onRetry: retry }))
      })
    } catch (err) {
      const until = err.until ? ` ${err.status === 423 ? 'The tutor is back' : 'More frees up'} ${when(err.until)}.` : ''
      const final = [403, 409, 423, 429].includes(err.status)
      patchLast((m) => ({ ...m, error: err.message + until, onRetry: final ? null : retry }))
      if (err.status === 423 || err.status === 429) onCourseChange()
      if (err.status === 403) setEnded(err.message)
    } finally {
      setBusy(false)
      loadChats()
    }
  }

  useEffect(() => {
    loadChats()
    api.chat(chatId).then((c) => {
      setChat(c)
      setMessages(c.messages)
      setRule(c.rule)
      const first = takeFirstMessage(chatId)
      if (first && !c.messages.length && !startedFirst.current) {
        startedFirst.current = true
        ask(first)
      }
    }).catch(setLoadError)
  }, [chatId]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { bottom.current?.scrollIntoView({ block: 'end' }) }, [messages])

  const newChat = async () => {
    setMenuOpen(false)
    if (chat?.kind === 'chat' && messages.length === 0) return
    const c = await api.newChat(course.id)
    navigate(`/c/${course.id}/chat/${c.id}`)
  }

  const onKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(input) }
  }
  const onInput = (e) => { setInput(e.target.value); saveDraft(chatId, e.target.value) }

  if (loadError) {
    return (
      <div className="content"><div className="narrow">
        <Banner kind="error">{loadError.status === 404 ? 'This chat doesn’t exist.' : loadError.message}</Banner>
        <a className="link" href={home}>Back to the course</a>
      </div></div>
    )
  }

  return (
    <div className="app">
      <aside className={`sidebar ${menuOpen ? 'open' : ''}`}>
        <a className="link backlink" href={home}>← Course home</a>
        <button className="primary" onClick={newChat}>+ New chat</button>
        <nav aria-label="Chats" className="chatlist">
          {chats.map((c) => (
            <a key={c.id} className={`chatitem ${c.id === chatId ? 'active' : ''}`} href={`#/c/${course.id}/chat/${c.id}`}
               onClick={() => setMenuOpen(false)}>
              {c.title}
            </a>
          ))}
        </nav>
      </aside>

      <main className="main">
        <header className="chathead">
          <button className="link mobile-only" onClick={() => setMenuOpen((v) => !v)} aria-label="Toggle chat list">☰</button>
          <div className="chathead-text">
            <strong className="chattitle">{chat?.title || ' '}</strong>
            {preview && <Badge>Preview</Badge>}
            {rule && (
              <div className="ruleline">
                <Badge tone={modeTone(rule.mode)}>{rule.title} · {rule.label}</Badge>
              </div>
            )}
          </div>
        </header>
        {course.pause?.active && <div className="chatbanner"><PauseBanner pause={course.pause} /></div>}
        {ended && <div className="chatbanner"><Banner kind="error" action={<a className="link" href="#/">My courses</a>}>{ended}</Banner></div>}
        <div className="scroll" role="log" aria-live="polite" aria-label="Conversation">
          {messages.length === 0 ? (
            <div className="welcome">
              <h1>{chat?.kind === 'pset' ? chat.title : 'What are you studying?'}</h1>
              <p className="muted">{INTRO[chat?.kind || 'chat']}</p>
              {chat?.kind === 'chat' && course.starter_questions?.length > 0 && (
                <div className="suggest">
                  {course.starter_questions.map((s) => (
                    <button key={s} className="suggestion" onClick={() => ask(s)}>{s}</button>
                  ))}
                </div>
              )}
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
            placeholder={course.pause?.active ? 'The tutor is paused' : 'Ask a question…'}
            value={input}
            onChange={onInput}
            onKeyDown={onKey}
            rows={2}
            maxLength={8000}
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
