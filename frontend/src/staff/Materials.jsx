import { useCallback, useEffect, useRef, useState } from 'react'
import { api, fileUrl } from '../api.js'
import { Badge, Banner, ErrorText, Loading, Modal, useAction } from '../ui.jsx'

export const KINDS = [
  ['lecture_notes', 'Lecture notes'], ['reading', 'Reading'], ['class_prep', 'Class prep'],
  ['problem_set', 'Problem set'], ['solution', 'Solution'], ['other', 'Other'],
]
const STATUS = {
  processing: ['info', 'Processing'], ready: ['good', 'Ready'], failed: ['bad', 'Failed'], no_text: ['bad', 'No text found'],
}

function PsetChecklist({ psets, value, onChange }) {
  if (!psets.length) return <p className="muted small">No problem sets yet. You can link this solution later.</p>
  const toggle = (id) => onChange(value.includes(id) ? value.filter((x) => x !== id) : [...value, id])
  return (
    <fieldset className="checks">
      <legend>Problem sets this file covers (leave empty to link later)</legend>
      {psets.map((p) => (
        <label key={p.id} className="checkline">
          <input type="checkbox" checked={value.includes(p.id)} onChange={() => toggle(p.id)} /> {p.title}
        </label>
      ))}
    </fieldset>
  )
}

function UploadForm({ course, psets, limits, onDone }) {
  const [kind, setKind] = useState('')
  const [files, setFiles] = useState([])
  const [links, setLinks] = useState([])
  const [rights, setRights] = useState(false)
  const { busy, error, run } = useAction()
  const submit = (e) => {
    e.preventDefault()
    run(async () => {
      const form = new FormData()
      form.append('kind', kind)
      form.append('rights', rights ? 'true' : 'false')
      form.append('pset_ids', JSON.stringify(kind === 'solution' ? links : []))
      files.forEach((f) => form.append('files', f))
      await api.upload(course.id, form)
      onDone()
    })
  }
  return (
    <form onSubmit={submit} className="upload">
      <label htmlFor="kind">1. Category</label>
      <select id="kind" value={kind} onChange={(e) => setKind(e.target.value)} required>
        <option value="">Choose a category first</option>
        {KINDS.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
      </select>
      {kind === 'solution' && (
        <Banner kind="warning">Solutions are tutor-only: never shown or cited to students until every problem set they cover is set to “Solutions open”.</Banner>
      )}
      <label htmlFor="files">2. Files (PDF, .txt or .md, up to {limits?.max_mb || 20} MB each)</label>
      <input id="files" type="file" multiple accept=".pdf,.txt,.md" disabled={!kind}
             onChange={(e) => setFiles([...e.target.files])} />
      {kind === 'solution' && <PsetChecklist psets={psets} value={links} onChange={setLinks} />}
      <label className="checkline">
        <input type="checkbox" checked={rights} onChange={(e) => setRights(e.target.checked)} />
        I have the right to use these materials in this course.
      </label>
      <ErrorText error={error} />
      <button className="primary" type="submit" disabled={busy || !kind || !files.length || !rights}>
        {busy ? 'Uploading…' : `Upload ${files.length || ''} file${files.length === 1 ? '' : 's'}`}
      </button>
    </form>
  )
}

function Row({ m, course, psets, reload, onLinks }) {
  const [renaming, setRenaming] = useState(false)
  const [title, setTitle] = useState(m.title)
  const replaceInput = useRef(null)
  const { busy, error, run } = useAction()
  const act = (fn) => run(async () => { await fn(); await reload() })
  const [tone, label] = STATUS[m.status] || ['neutral', m.status]
  const links = m.kind === 'solution' ? m.psets : m.kind === 'problem_set' ? m.solutions : null

  const replace = (e) => {
    const f = e.target.files[0]
    if (!f) return
    const form = new FormData()
    form.append('file', f)
    act(() => api.replaceFile(course.id, m.id, form))
  }

  return (
    <tr>
      <td>
        {renaming ? (
          <form className="inline" onSubmit={(e) => { e.preventDefault(); act(async () => { await api.updateMaterial(course.id, m.id, { title }); setRenaming(false) }) }}>
            <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} aria-label="Title" />
            <button className="secondary small" type="submit">Save</button>
          </form>
        ) : (
          <>
            <span className="doctitle">{m.title}</span>
            <span className="muted small block">{m.file_name}{m.pages ? ` · ${m.pages} p.` : ''}</span>
          </>
        )}
        {m.warning && <p className="warning small">⚠ {m.warning}</p>}
        <ErrorText error={error} />
      </td>
      <td>
        <select aria-label={`Category of ${m.title}`} value={m.kind} disabled={busy}
                onChange={(e) => act(() => api.updateMaterial(course.id, m.id, { kind: e.target.value }))}>
          {KINDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
      </td>
      <td>
        <Badge tone={tone}>{label}</Badge>
        {m.status_detail && <span className="muted small block">{m.status_detail}</span>}
        {m.kind === 'solution' && <span className="muted small block">{m.public ? 'Released to students' : 'Tutor-only'}</span>}
      </td>
      <td>
        {links && (links.length ? links.map((l) => <span key={l.id} className="block small">{l.title}</span>)
          : <span className="muted small">{m.kind === 'solution' ? 'Not linked' : 'No solution'}</span>)}
        {m.kind === 'solution' && psets.length > 0 && (
          <button className="link small" onClick={() => onLinks(m)}>Edit links</button>
        )}
      </td>
      <td className="actions">
        <a className="link small" href={fileUrl(m.url)} target="_blank" rel="noreferrer">Open</a>
        <button className="link small" onClick={() => setRenaming((v) => !v)}>{renaming ? 'Cancel' : 'Rename'}</button>
        <button className="link small" onClick={() => replaceInput.current?.click()} disabled={busy}>Replace</button>
        <input ref={replaceInput} type="file" accept=".pdf,.txt,.md" hidden onChange={replace} />
        {(m.status === 'failed' || m.status === 'no_text') && (
          <button className="link small" onClick={() => act(() => api.retryMaterial(course.id, m.id))}>Retry</button>
        )}
        <button className="link small danger" disabled={busy}
                onClick={() => window.confirm(`Delete “${m.title}”? It will disappear from the tutor and from future citations.`)
                  && act(() => api.deleteMaterial(course.id, m.id))}>Delete</button>
      </td>
    </tr>
  )
}

export default function Materials({ course, reload: reloadCourse }) {
  const [items, setItems] = useState(null)
  const [limits, setLimits] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [linking, setLinking] = useState(null)
  const [links, setLinks] = useState([])
  const [filter, setFilter] = useState('')
  const [loadError, setLoadError] = useState(null)

  const load = useCallback(async () => {
    try {
      const r = await api.materials(course.id)
      setItems(r.materials)
      setLimits(r.limits)
    } catch (e) {
      setLoadError(e)
    }
  }, [course.id])
  useEffect(() => { load() }, [load])
  useEffect(() => { // keep polling while files are processing
    if (!items?.some((m) => m.status === 'processing')) return undefined
    const t = setTimeout(async () => { await load(); reloadCourse() }, 2000)
    return () => clearTimeout(t)
  }, [items, load, reloadCourse])

  if (loadError) return <ErrorText error={loadError} />
  if (!items) return <Loading />
  const psets = items.filter((m) => m.kind === 'problem_set')
  const shown = filter ? items.filter((m) => m.kind === filter) : items
  const refresh = async () => { await load(); reloadCourse() }

  return (
    <div>
      <div className="row-between">
        <h2>Course materials</h2>
        <button className="primary" onClick={() => setUploading(true)}>Upload</button>
      </div>
      <p className="muted small">
        {items.length} of {limits?.files} files. The category you pick decides what students can see; the warning check never changes it.
      </p>
      {items.length > 0 && (
        <label className="filter">Show{' '}
          <select value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="">All categories</option>
            {KINDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
        </label>
      )}
      {items.length === 0 ? (
        <div className="empty card"><p>No materials yet. Upload lecture notes, readings and problem sets to open the tutor.</p></div>
      ) : (
        <div className="tablewrap">
          <table className="table">
            <thead><tr><th>Title</th><th>Category</th><th>Status</th><th>Linked</th><th>Actions</th></tr></thead>
            <tbody>
              {shown.map((m) => (
                <Row key={m.id} m={m} course={course} psets={psets} reload={refresh}
                     onLinks={(doc) => { setLinking(doc); setLinks(doc.psets.map((p) => p.id)) }} />
              ))}
            </tbody>
          </table>
        </div>
      )}
      {uploading && (
        <Modal title="Upload materials" onClose={() => setUploading(false)}>
          <UploadForm course={course} psets={psets} limits={limits} onDone={async () => { setUploading(false); await refresh() }} />
        </Modal>
      )}
      {linking && (
        <Modal title={`Link “${linking.title}”`} onClose={() => setLinking(null)}>
          <PsetChecklist psets={psets} value={links} onChange={setLinks} />
          <button className="primary" onClick={async () => {
            await api.updateMaterial(course.id, linking.id, { pset_ids: links })
            setLinking(null)
            await refresh()
          }}>Save links</button>
        </Modal>
      )}
    </div>
  )
}
