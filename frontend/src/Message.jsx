import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'

// Models sometimes emit \( \) and \[ \]; normalise to $ and $$ for remark-math.
function prepare(text) {
  return text
    .replace(/\\\[([\s\S]+?)\\\]/g, (_, m) => `$$${m}$$`)
    .replace(/\\\(([\s\S]+?)\\\)/g, (_, m) => `$${m}$`)
    .replace(/\[S(\d+)\]/g, (_, n) => `[${n}](#cite-${n})`)
}

export function Markdown({ text, citations = [], onCite }) {
  const byN = Object.fromEntries(citations.map((c) => [String(c.n), c]))
  return (
    <ReactMarkdown
      remarkPlugins={[remarkMath]}
      rehypePlugins={[rehypeKatex]}
      components={{
        a({ href, children }) {
          const m = /^#cite-(\d+)$/.exec(href || '')
          if (!m) return <a href={href} target="_blank" rel="noreferrer">{children}</a>
          const c = byN[m[1]]
          if (!c) return null
          return (
            <button
              type="button"
              className="chip"
              onClick={() => onCite(c)}
              aria-label={`Source ${c.n}: ${c.title}, page ${c.page}`}
            >
              {c.n}
            </button>
          )
        },
      }}
    >
      {prepare(text)}
    </ReactMarkdown>
  )
}

export default function Message({ m, onCite, onIllustrate, illustrating }) {
  if (m.role === 'user') {
    return (
      <div className="msg user">
        <div className="who">You</div>
        <div className="bubble">{m.content}</div>
      </div>
    )
  }
  return (
    <div className="msg tutor">
      <div className="who">
        BruinBuddy <span className="tag">AI-generated</span>
      </div>
      <div className="bubble">
        <Markdown text={m.content} citations={m.citations} onCite={onCite} />
        {m.error && (
          <p className="error" role="alert">
            {m.error} {m.onRetry && <button className="link" onClick={m.onRetry}>Retry</button>}
          </p>
        )}
      </div>
      <div className="msg-footer">
        {onIllustrate && m.content && !m.error && (
          <button
            type="button"
            className="chip-btn illustrate-msg-btn"
            onClick={() => onIllustrate(m)}
            disabled={illustrating}
          >
            Illustrate this
          </button>
        )}
        {m.memory_used?.length > 0 && (
          <details className="memory">
            <summary>Used memory from past chats</summary>
            <ul>{m.memory_used.map((n) => <li key={n.id}>{n.text}</li>)}</ul>
          </details>
        )}
      </div>
    </div>
  )
}
