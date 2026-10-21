import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { Banner, ErrorText, Loading, useAction } from '../ui.jsx'

const STARTERS = [
  'Tone: patient and encouraging; keep answers short.',
  'Use R for simulations and show the code.',
  'Use the notation from the lecture notes (for example P(A | B)).',
  'For grading, extension or exam logistics questions, tell students to ask the course staff.',
  'Only help with topics covered in this course.',
]

function DocPicker({ docs, value, onChange }) {
  const toggle = (id) => onChange(value.includes(id) ? value.filter((x) => x !== id) : [...value, id])
  const names = docs.filter((d) => value.includes(d.id)).map((d) => d.title)
  return (
    <details className="docpicker">
      <summary>{names.length ? `Applies to: ${names.join(', ')}` : 'Choose the materials it applies to'}</summary>
      <div className="checks scrollbox">
        {docs.map((d) => (
          <label key={d.id} className="checkline">
            <input type="checkbox" checked={value.includes(d.id)} onChange={() => toggle(d.id)} /> {d.title}
            <span className="muted small"> · {d.kind_label}</span>
          </label>
        ))}
      </div>
    </details>
  )
}

export default function Guidelines({ course, reload }) {
  const [data, setData] = useState(null)
  const [docs, setDocs] = useState([])
  const [saved, setSaved] = useState(false)
  const { busy, error, run, setError } = useAction()

  useEffect(() => {
    api.guidelines(course.id).then(setData).catch(setError)
    api.materials(course.id).then((r) => setDocs(r.materials.filter((m) => m.status === 'ready'))).catch(() => {})
  }, [course.id, setError])

  if (!data) return error ? <ErrorText error={error} /> : <Loading />
  const { limits } = data
  const update = (patch) => { setData({ ...data, ...patch }); setSaved(false) }
  const setTagged = (i, patch) => update({ tagged: data.tagged.map((g, j) => (j === i ? { ...g, ...patch } : g)) })

  const loadFile = (e) => {
    const f = e.target.files[0]
    if (!f) return
    const reader = new FileReader()
    reader.onload = () => update({ general: String(reader.result).slice(0, limits.general) })
    reader.readAsText(f)
    e.target.value = ''
  }

  const save = () => run(async () => {
    const tagged = data.tagged.filter((g) => g.text.trim()).map((g) => ({ text: g.text, doc_ids: g.doc_ids }))
    if (tagged.some((g) => !g.doc_ids.length)) throw new Error('Choose at least one material for each additional guideline.')
    await api.saveGuidelines(course.id, { general: data.general, tagged })
    setSaved(true)
    reload()
  })

  return (
    <div className="guidelines">
      <h2>Teaching guidelines</h2>
      <Banner>
        Guidelines shape tone, tools, notation and scope. They can’t unlock solutions, turn off citations or change a
        problem set’s mode; the tutor’s safety rules always come first. Students never see guidelines.
      </Banner>

      <label htmlFor="general"><strong>General guideline</strong> (applies to every answer)</label>
      <div className="chips">
        {STARTERS.map((s) => (
          <button key={s} type="button" className="chip-btn"
                  onClick={() => update({ general: (data.general ? data.general.trimEnd() + '\n' : '') + s })}>+ {s}</button>
        ))}
      </div>
      <textarea id="general" rows={7} value={data.general} maxLength={limits.general}
                onChange={(e) => update({ general: e.target.value })}
                placeholder="For example: Use R for simulations. Keep hints short. Refer grading questions to the TAs." />
      <div className="row-between small">
        <label className="link">Load from a .txt or .md file<input type="file" accept=".txt,.md,text/plain,text/markdown" hidden onChange={loadFile} /></label>
        <span className="muted">{data.general.length} / {limits.general}</span>
      </div>

      <h3>Additional guidelines for specific materials</h3>
      <p className="muted small">Used when that material is among the sources for an answer or is the student’s problem set. For that material, they win over the general guideline.</p>
      {data.tagged.map((g, i) => (
        <div key={g.id ?? `new${i}`} className="card tagged">
          <DocPicker docs={docs} value={g.doc_ids} onChange={(doc_ids) => setTagged(i, { doc_ids })} />
          <textarea rows={3} value={g.text} maxLength={limits.tagged} aria-label={`Additional guideline ${i + 1}`}
                    onChange={(e) => setTagged(i, { text: e.target.value })}
                    placeholder="For example: Problem 3 expects an R simulation." />
          <div className="row-between small">
            <button className="link danger" onClick={() => update({ tagged: data.tagged.filter((_, j) => j !== i) })}>Remove</button>
            <span className="muted">{g.text.length} / {limits.tagged}</span>
          </div>
        </div>
      ))}
      <button className="secondary" disabled={data.tagged.length >= limits.count || !docs.length}
              onClick={() => update({ tagged: [...data.tagged, { text: '', doc_ids: [] }] })}>
        + Add a guideline for specific materials
      </button>

      <div className="savebar">
        <button className="primary" onClick={save} disabled={busy}>{busy ? 'Saving…' : 'Save guidelines'}</button>
        {saved && <span className="muted">Saved. They apply from the next message.</span>}
        <ErrorText error={error} />
      </div>
    </div>
  )
}
