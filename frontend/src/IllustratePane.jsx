import { useEffect, useRef, useState } from 'react'
import { api } from './api.js'
import { Badge, Banner, Modal } from './ui.jsx'

const SKILL_OPTIONS = [
  { value: 'auto', label: 'Auto (Smart Skill Router)' },
  { value: 'manim_3b1b', label: 'Manim 3B1B · Math & Distributions' },
  { value: 'anatomy_isometric', label: 'Anatomy · Isometric Apparatus' },
  { value: 'explainer_diagram', label: 'Diagram Animation · Flowchart' },
  { value: 'explainer_storyboard', label: 'Explainer Video · Whiteboard' },
]

function slugify(text) {
  return (text || 'bruinbuddy-illustration')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 48) || 'illustration'
}

function triggerBlobDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 2000)
}

function triggerDataUrlDownload(dataUrl, filename) {
  const a = document.createElement('a')
  a.href = dataUrl
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
}

export default function IllustratePane({
  illustrations = [],
  active,
  onSelect,
  onGenerate,
  generating,
  error,
  hasMessages,
  paused,
  onClose,
}) {
  const [skill, setSkill] = useState('auto')
  const [customPrompt, setCustomPrompt] = useState('')
  const [expanded, setExpanded] = useState(false)
  const [recordingVideo, setRecordingVideo] = useState(false)
  const [exportStatus, setExportStatus] = useState('')
  const iframeRef = useRef(null)
  const modalIframeRef = useRef(null)

  useEffect(() => {
    const onMessage = (ev) => {
      if (!ev.data || !ev.data.type || !active) return
      const slug = slugify(active.title)
      if (ev.data.type === 'bb_export_result') {
        setRecordingVideo(false)
        setExportStatus('')
        const ext = ev.data.format === 'webm' ? 'webm' : 'png'
        triggerDataUrlDownload(ev.data.url, `${slug}.${ext}`)
      } else if (ev.data.type === 'bb_export_error') {
        setRecordingVideo(false)
        setExportStatus('Video capture unsupported in this browser; download the Interactive HTML instead.')
      }
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [active])

  const submitGenerate = (e) => {
    e.preventDefault()
    if (generating || paused || (!hasMessages && !customPrompt.trim())) return
    onGenerate({ preferred_skill: skill, prompt: customPrompt.trim() || null })
  }

  const downloadHtml = () => {
    if (!active) return
    const blob = new Blob([active.artifact_html], { type: 'text/html;charset=utf-8' })
    triggerBlobDownload(blob, `${slugify(active.title)}.html`)
  }

  const downloadManim = () => {
    if (!active?.manim_code) return
    const blob = new Blob([active.manim_code], { type: 'text/x-python;charset=utf-8' })
    triggerBlobDownload(blob, `${slugify(active.title)}_manim.py`)
  }

  const downloadSvg = async () => {
    if (!active) return
    try {
      const blob = await api.downloadIllustration(active.id, 'svg')
      triggerBlobDownload(blob, `${slugify(active.title)}.svg`)
    } catch {
      setExportStatus('Could not export SVG.')
    }
  }

  const requestCanvasExport = (type) => {
    const target = (expanded && modalIframeRef.current?.contentWindow) || iframeRef.current?.contentWindow
    if (!target) return
    if (type === 'bb_export_webm') {
      setRecordingVideo(true)
      setExportStatus('Recording 4.5s animation clip…')
    }
    target.postMessage({ type }, '*')
  }

  return (
    <div className="illustrate-pane">
      <div className="srchead">
        <strong>Illustrate Concept</strong>
        {onClose && (
          <button className="link" onClick={onClose} aria-label="Close illustrate panel">×</button>
        )}
      </div>

      <form className="illustrate-form" onSubmit={submitGenerate}>
        <label className="small muted" htmlFor="ill-skill-select">Visual Skill Engine</label>
        <select
          id="ill-skill-select"
          value={skill}
          onChange={(e) => setSkill(e.target.value)}
          disabled={generating || paused}
        >
          {SKILL_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <input
          type="text"
          placeholder="Optional: specific concept or question to visualize…"
          value={customPrompt}
          onChange={(e) => setCustomPrompt(e.target.value)}
          disabled={generating || paused}
          maxLength={300}
        />
        <button
          className="primary small"
          type="submit"
          disabled={generating || paused || (!hasMessages && !customPrompt.trim())}
        >
          {generating ? 'Building animation…' : (active ? 'Generate New Illustration' : 'Illustrate Current Concept')}
        </button>
      </form>

      {error && <Banner kind="error">{error}</Banner>}
      {!hasMessages && !active && (
        <p className="muted small">
          Ask BruinBuddy to explain a concept in the chat (or type a topic above), then click <strong>Illustrate</strong> to generate an interactive animation.
        </p>
      )}

      {active && (
        <div className="illustrate-card">
          <div className="illustrate-meta">
            <div className="inline wrap">
              <Badge tone="good">{active.skill_meta?.label || active.skill}</Badge>
              <Badge tone="info">{active.skill_meta?.modality_label || active.modality}</Badge>
            </div>
            <p className="srctitle">{active.title}</p>
            {active.rationale && <p className="muted small illustrate-rationale">{active.rationale}</p>}
          </div>

          <div className="illustrate-stage-box">
            <iframe
              ref={iframeRef}
              title={active.title}
              className="illustrate-iframe"
              sandbox="allow-scripts allow-downloads"
              srcDoc={active.artifact_html}
            />
          </div>

          <div className="illustrate-actions">
            <div className="inline wrap">
              <button
                type="button"
                className="secondary small"
                onClick={() => setExpanded(true)}
              >
                Expand Player
              </button>
              <button
                type="button"
                className="primary small"
                onClick={downloadHtml}
                title="Download self-contained interactive HTML animation"
              >
                Download HTML
              </button>
              <button
                type="button"
                className="secondary small"
                onClick={() => requestCanvasExport('bb_export_webm')}
                disabled={recordingVideo}
                title="Record and download .webm video clip"
              >
                {recordingVideo ? 'Recording…' : 'Video (.webm)'}
              </button>
              <button
                type="button"
                className="secondary small"
                onClick={() => requestCanvasExport('bb_export_png')}
                title="Download PNG snapshot"
              >
                PNG
              </button>
              <button
                type="button"
                className="secondary small"
                onClick={downloadSvg}
                title="Download vector SVG summary"
              >
                SVG
              </button>
              {active.manim_code && (
                <button
                  type="button"
                  className="secondary small"
                  onClick={downloadManim}
                  title="Download runnable Manim Community Edition Python script"
                >
                  Manim (.py)
                </button>
              )}
            </div>
            {exportStatus && <p className="muted small">{exportStatus}</p>}
          </div>
        </div>
      )}

      {illustrations.length > 1 && (
        <div className="illustrate-history">
          <div className="section-title">Saved in this chat ({illustrations.length})</div>
          <div className="illustrate-list">
            {illustrations.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`illustrate-item ${active?.id === item.id ? 'active' : ''}`}
                onClick={() => onSelect(item)}
              >
                <span className="illustrate-item-title">{item.title}</span>
                <span className="muted small">{item.skill_meta?.label || item.skill}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {expanded && active && (
        <Modal title={active.title} onClose={() => setExpanded(false)} wide>
          <div className="inline wrap" style={{ marginBottom: 8 }}>
            <Badge tone="good">{active.skill_meta?.label || active.skill}</Badge>
            <Badge tone="info">{active.skill_meta?.modality_label || active.modality}</Badge>
            <span className="muted small">{active.rationale}</span>
          </div>
          <div className="illustrate-stage-box expanded">
            <iframe
              ref={modalIframeRef}
              title={`${active.title} (Expanded)`}
              className="illustrate-iframe expanded"
              sandbox="allow-scripts allow-downloads"
              srcDoc={active.artifact_html}
            />
          </div>
          <div className="row-between" style={{ marginTop: 12 }}>
            <div className="inline wrap">
              <button type="button" className="primary small" onClick={downloadHtml}>
                Download Interactive HTML
              </button>
              <button
                type="button"
                className="secondary small"
                onClick={() => requestCanvasExport('bb_export_webm')}
                disabled={recordingVideo}
              >
                {recordingVideo ? 'Recording 4.5s…' : 'Download Video (.webm)'}
              </button>
              <button type="button" className="secondary small" onClick={() => requestCanvasExport('bb_export_png')}>
                Download Image (.png)
              </button>
              <button type="button" className="secondary small" onClick={downloadSvg}>
                Download Vector (.svg)
              </button>
              {active.manim_code && (
                <button type="button" className="secondary small" onClick={downloadManim}>
                  Download Manim Script (.py)
                </button>
              )}
            </div>
            <button type="button" className="secondary small" onClick={() => setExpanded(false)}>
              Close
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}
