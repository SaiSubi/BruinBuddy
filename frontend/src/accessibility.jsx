import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { Modal } from './ui.jsx'

const STORAGE_KEY = 'bb_a11y_prefs'

const DEFAULT_PREFS = {
  theme: 'light', // 'light' | 'dark' | 'high-contrast' | 'system'
  colorblind: 'none', // 'none' | 'protanopia' | 'deuteranopia' | 'tritanopia' | 'monochrome'
  dyslexia: false,
  paperTint: 'none', // 'none' | 'cream' | 'sage' | 'sky'
  fontScale: '100', // '100' | '110' | '120' | '130'
  underlineLinks: false,
  reducedMotion: false,
}

const AccessibilityContext = createContext(null)

function loadPrefs() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULT_PREFS
    const parsed = JSON.parse(raw)
    return { ...DEFAULT_PREFS, ...parsed }
  } catch {
    return DEFAULT_PREFS
  }
}

function savePrefs(prefs) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs))
  } catch {
    /* ignore storage quota errors */
  }
}

export function AccessibilityProvider({ children }) {
  const [prefs, setPrefs] = useState(loadPrefs)
  const [readerOpen, setReaderOpen] = useState(false)
  const [readerCustom, setReaderCustom] = useState(null) // optional { title, blocks }
  const [a11yModalOpen, setA11yModalOpen] = useState(false)

  const updatePref = useCallback((key, value) => {
    setPrefs((prev) => {
      const next = { ...prev, [key]: value }
      savePrefs(next)
      return next
    })
  }, [])

  const applyPreset = useCallback((preset) => {
    setPrefs(() => {
      let next = { ...DEFAULT_PREFS }
      if (preset === 'dyslexia') {
        next = { ...DEFAULT_PREFS, dyslexia: true, paperTint: 'cream', fontScale: '110' }
      } else if (preset === 'protanopia') {
        next = { ...DEFAULT_PREFS, colorblind: 'protanopia', underlineLinks: true }
      } else if (preset === 'tritanopia') {
        next = { ...DEFAULT_PREFS, colorblind: 'tritanopia', underlineLinks: true }
      } else if (preset === 'high-contrast') {
        next = { ...DEFAULT_PREFS, theme: 'high-contrast', underlineLinks: true, fontScale: '110' }
      } else if (preset === 'dark') {
        next = { ...DEFAULT_PREFS, theme: 'dark' }
      }
      savePrefs(next)
      return next
    })
  }, [])

  const resetPrefs = useCallback(() => {
    savePrefs(DEFAULT_PREFS)
    setPrefs(DEFAULT_PREFS)
  }, [])

  const openImmersiveReader = useCallback((custom = null) => {
    setReaderCustom(custom)
    setReaderOpen(true)
  }, [])

  useEffect(() => {
    const root = document.documentElement
    const media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null

    const applyTheme = () => {
      const resolvedTheme =
        prefs.theme === 'system' ? (media?.matches ? 'dark' : 'light') : prefs.theme
      root.setAttribute('data-theme', resolvedTheme)
      root.setAttribute('data-theme-pref', prefs.theme)
    }

    applyTheme()
    root.setAttribute('data-colorblind', prefs.colorblind || 'none')
    root.setAttribute('data-dyslexia', prefs.dyslexia ? 'true' : 'false')
    root.setAttribute('data-paper-tint', prefs.paperTint || 'none')
    root.setAttribute('data-font-scale', prefs.fontScale || '100')
    root.setAttribute('data-underline-links', prefs.underlineLinks ? 'true' : 'false')
    root.setAttribute('data-reduced-motion', prefs.reducedMotion ? 'true' : 'false')

    if (prefs.theme === 'system' && media?.addEventListener) {
      media.addEventListener('change', applyTheme)
      return () => media.removeEventListener('change', applyTheme)
    }
    return undefined
  }, [prefs])

  const activeBadgeCount = useMemo(() => {
    let count = 0
    if (prefs.theme !== 'light') count++
    if (prefs.colorblind !== 'none') count++
    if (prefs.dyslexia) count++
    if (prefs.paperTint !== 'none') count++
    if (prefs.fontScale !== '100') count++
    if (prefs.underlineLinks) count++
    if (prefs.reducedMotion) count++
    return count
  }, [prefs])

  const value = useMemo(
    () => ({
      prefs,
      updatePref,
      applyPreset,
      resetPrefs,
      activeBadgeCount,
      openImmersiveReader,
      openA11yModal: () => setA11yModalOpen(true),
      closeA11yModal: () => setA11yModalOpen(false),
    }),
    [prefs, updatePref, applyPreset, resetPrefs, activeBadgeCount, openImmersiveReader]
  )

  return (
    <AccessibilityContext.Provider value={value}>
      {children}
      {readerOpen && (
        <ImmersiveReaderModal
          custom={readerCustom}
          prefs={prefs}
          updatePref={updatePref}
          onClose={() => setReaderOpen(false)}
        />
      )}
      {a11yModalOpen && (
        <Modal title="Appearance & Accessibility" wide onClose={() => setA11yModalOpen(false)}>
          <AccessibilityPanel />
        </Modal>
      )}
    </AccessibilityContext.Provider>
  )
}

export function useAccessibility() {
  const ctx = useContext(AccessibilityContext)
  if (!ctx) {
    return {
      prefs: DEFAULT_PREFS,
      updatePref: () => {},
      applyPreset: () => {},
      resetPrefs: () => {},
      activeBadgeCount: 0,
      openImmersiveReader: () => {},
      openA11yModal: () => {},
      closeA11yModal: () => {},
    }
  }
  return ctx
}

export function AccessibilityPanel() {
  const { prefs, updatePref, applyPreset, resetPrefs } = useAccessibility()

  return (
    <div className="a11y-panel" aria-label="Appearance and Accessibility Controls">
      <div className="a11y-section">
        <div className="row-between">
          <span className="a11y-label">Quick Presets</span>
          <button type="button" className="link small" onClick={resetPrefs}>
            Reset to UCLA defaults
          </button>
        </div>
        <div className="a11y-preset-row">
          <button type="button" className="chip-btn" onClick={() => applyPreset('default')}>
            UCLA Default
          </button>
          <button type="button" className="chip-btn" onClick={() => applyPreset('dark')}>
            Westwood Night
          </button>
          <button type="button" className="chip-btn" onClick={() => applyPreset('dyslexia')}>
            Dyslexia Friendly
          </button>
          <button type="button" className="chip-btn" onClick={() => applyPreset('protanopia')}>
            Red-Green Safe
          </button>
          <button type="button" className="chip-btn" onClick={() => applyPreset('tritanopia')}>
            Blue-Yellow Safe
          </button>
          <button type="button" className="chip-btn" onClick={() => applyPreset('high-contrast')}>
            High Contrast AAA
          </button>
        </div>
      </div>

      {/* 1. Theme / Appearance */}
      <div className="a11y-section">
        <span className="a11y-label">1. Appearance & Theme</span>
        <p className="muted small">Choose between UCLA Bruin Learn daylight, dark studio, or WCAG AAA high contrast.</p>
        <div className="a11y-theme-grid">
          {[
            { id: 'light', name: 'Light (Bruin Learn)', desc: 'UCLA Blue rail & crisp white canvas', swatch: 'swatch-light' },
            { id: 'dark', name: 'Dark (Westwood Night)', desc: 'Low-glare slate navy & luminous gold', swatch: 'swatch-dark' },
            { id: 'high-contrast', name: 'High Contrast (AAA)', desc: 'Maximum 7:1+ contrast & bold borders', swatch: 'swatch-hc' },
            { id: 'system', name: 'Sync with System', desc: 'Follow your OS light/dark schedule', swatch: 'swatch-sys' },
          ].map((t) => (
            <button
              key={t.id}
              type="button"
              className={`a11y-card-btn ${prefs.theme === t.id ? 'active' : ''}`}
              aria-pressed={prefs.theme === t.id}
              onClick={() => updatePref('theme', t.id)}
            >
              <div className={`a11y-swatch ${t.swatch}`} aria-hidden="true">
                <span className="sw-rail" />
                <span className="sw-body">
                  <span className="sw-hero" />
                  <span className="sw-line" />
                </span>
              </div>
              <strong>{t.name}</strong>
              <span className="muted small">{t.desc}</span>
            </button>
          ))}
        </div>
      </div>

      {/* 2. Colorblind Vision Modes */}
      <div className="a11y-section">
        <span className="a11y-label">2. Colorblind & Vision Palette</span>
        <p className="muted small">
          Recalibrates semantic badges, meters, and charts using colorblind-safe Okabe-Ito tokens and clear text labels.
        </p>
        <div className="a11y-choice-list">
          {[
            {
              id: 'none',
              title: 'Standard UCLA Vision',
              desc: 'Official UCLA Blue (#2774AE), Gold (#FFD100), and Canvas status colors.',
            },
            {
              id: 'protanopia',
              title: 'Protanopia / Deuteranopia (Red-Green Safe)',
              desc: 'Replaces red/green ambiguity with Okabe-Ito Blue (#0072B2), Amber (#E69F00), and Vermilion (#D55E00).',
            },
            {
              id: 'tritanopia',
              title: 'Tritanopia (Blue-Yellow Safe)',
              desc: 'Uses high-distinction Teal (#009E73), Magenta (#CC79A7), and Crimson (#D55E00) accents.',
            },
            {
              id: 'monochrome',
              title: 'Monochromacy / Achromatopsia Safe',
              desc: 'High-luminance grayscale separation with bold borders and explicit status labels.',
            },
          ].map((c) => (
            <button
              key={c.id}
              type="button"
              className={`a11y-row-btn ${prefs.colorblind === c.id ? 'active' : ''}`}
              aria-pressed={prefs.colorblind === c.id}
              onClick={() => updatePref('colorblind', c.id)}
            >
              <div>
                <strong>{c.title}</strong>
                <div className="muted small">{c.desc}</div>
              </div>
              <span className="a11y-check">{prefs.colorblind === c.id ? 'Active' : 'Select'}</span>
            </button>
          ))}
        </div>
        <div className="a11y-sample-badges" aria-label="Live colorblind badge preview">
          <span className="small muted">Live preview:</span>
          <span className="badge good">Open Practice</span>
          <span className="badge warn">Graded Rule</span>
          <span className="badge info">Course Note</span>
          <span className="badge bad">Limit Reached</span>
        </div>
      </div>

      {/* 3. Dyslexia & Reading Comfort */}
      <div className="a11y-section">
        <span className="a11y-label">3. Dyslexia & Reading Comfort</span>
        <label className="a11y-toggle-row">
          <div>
            <strong>Dyslexia-Friendly Typography & Spacing</strong>
            <div className="muted small">
              Applies Lexend and Atkinson Hyperlegible letterforms, wider letter spacing (0.055em), word spacing (0.14em), 1.82 line height, and disables italics.
            </div>
          </div>
          <input
            type="checkbox"
            checked={Boolean(prefs.dyslexia)}
            onChange={(e) => updatePref('dyslexia', e.target.checked)}
          />
        </label>

        <div className="a11y-subrow">
          <span className="small"><strong>Reading Surface Tint</strong> (reduces visual stress / glare):</span>
          <div className="segmented">
            {[
              ['none', 'White'],
              ['cream', 'Warm Cream'],
              ['sage', 'Soft Sage'],
              ['sky', 'Cool Sky'],
            ].map(([val, label]) => (
              <button
                key={val}
                type="button"
                className={prefs.paperTint === val ? 'active' : ''}
                onClick={() => updatePref('paperTint', val)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 4. Font Scale, Links & Motion */}
      <div className="a11y-section">
        <span className="a11y-label">4. Text Size, Navigation Cues & Motion</span>
        <div className="a11y-subrow">
          <span className="small"><strong>Text Scaling:</strong></span>
          <div className="segmented">
            {[
              ['100', '100% (Default)'],
              ['110', '110% (Medium)'],
              ['120', '120% (Large)'],
              ['130', '130% (Extra Large)'],
            ].map(([val, label]) => (
              <button
                key={val}
                type="button"
                className={prefs.fontScale === val ? 'active' : ''}
                onClick={() => updatePref('fontScale', val)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <label className="a11y-toggle-row">
          <div>
            <strong>Always Underline Links & Interactive Controls</strong>
            <div className="muted small">Makes clickable links and navigation items unmistakable without relying on color.</div>
          </div>
          <input
            type="checkbox"
            checked={Boolean(prefs.underlineLinks)}
            onChange={(e) => updatePref('underlineLinks', e.target.checked)}
          />
        </label>

        <label className="a11y-toggle-row">
          <div>
            <strong>Reduced Motion</strong>
            <div className="muted small">Minimizes UI transitions and smooth-scroll animations across the workspace.</div>
          </div>
          <input
            type="checkbox"
            checked={Boolean(prefs.reducedMotion)}
            onChange={(e) => updatePref('reducedMotion', e.target.checked)}
          />
        </label>
      </div>
    </div>
  )
}

function extractReadableBlocks() {
  const container =
    document.querySelector('.canvas-main-stage') ||
    document.querySelector('.main') ||
    document.querySelector('.content') ||
    document.body
  const titleEl = container.querySelector('h1, .chattitle, .ucla-hero-title')
  const title = titleEl ? titleEl.textContent.trim() : 'Course Study View'

  const nodes = container.querySelectorAll(
    '.msg .bubble, .ucla-welcome-body p, .canvas-row-title, .accordion-panel, .srctext, p, li'
  )
  const seen = new Set()
  const blocks = []
  nodes.forEach((n) => {
    if (n.closest('.a11y-panel') || n.closest('.canvas-rail') || n.closest('.canvas-top-header')) return
    const text = (n.innerText || n.textContent || '').replace(/\s+/g, ' ').trim()
    if (text.length >= 18 && !seen.has(text)) {
      seen.add(text)
      blocks.push(text)
    }
  })

  if (!blocks.length) {
    blocks.push(
      'Welcome to UCLA BruinBuddy Immersive Reader. Open any course module, problem set, or AI Tutor conversation and click Immersive Reader to listen aloud or read with line focus and dyslexia-friendly spacing.'
    )
  }
  return { title, blocks: blocks.slice(0, 40) }
}

function ImmersiveReaderModal({ custom, prefs, updatePref, onClose }) {
  const content = useMemo(() => custom || extractReadableBlocks(), [custom])
  const [activeIndex, setActiveIndex] = useState(0)
  const [lineFocus, setLineFocus] = useState(false)
  const [syllables, setSyllables] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const [rate, setRate] = useState(1.0)

  const stopSpeech = useCallback(() => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel()
    }
    setSpeaking(false)
  }, [])

  useEffect(() => () => stopSpeech(), [stopSpeech])

  const speakAt = (idx) => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return
    window.speechSynthesis.cancel()
    const text = content.blocks[idx]
    if (!text) return
    const utter = new SpeechSynthesisUtterance(text)
    utter.rate = rate
    utter.onend = () => {
      if (idx + 1 < content.blocks.length) {
        setActiveIndex(idx + 1)
        speakAt(idx + 1)
      } else {
        setSpeaking(false)
      }
    }
    utter.onerror = () => setSpeaking(false)
    setActiveIndex(idx)
    setSpeaking(true)
    window.speechSynthesis.speak(utter)
  }

  const toggleSpeak = () => {
    if (speaking) {
      stopSpeech()
    } else {
      speakAt(activeIndex)
    }
  }

  const formatSyllables = (text) => {
    if (!syllables) return text
    return text
      .split(' ')
      .map((w) => (w.length > 6 ? w.replace(/([aeiouy]{1,2}[^aeiouy\s]{1,2})(?=[a-z]{2})/gi, '$1·') : w))
      .join('  ')
  }

  return (
    <Modal title={`Immersive Reader — ${content.title}`} wide onClose={onClose}>
      <div className="immersive-reader">
        <div className="immersive-toolbar">
          <div className="inline wrap">
            <button type="button" className="primary small" onClick={toggleSpeak}>
              {speaking ? 'Stop Read Aloud' : 'Read Aloud'}
            </button>
            <label className="small inline">
              Speed:
              <select
                value={rate}
                onChange={(e) => setRate(Number(e.target.value))}
                aria-label="Speech speed"
              >
                <option value={0.8}>0.8x</option>
                <option value={1.0}>1.0x</option>
                <option value={1.25}>1.25x</option>
                <option value={1.5}>1.5x</option>
              </select>
            </label>
            <button
              type="button"
              className={`secondary small ${lineFocus ? 'active-pill' : ''}`}
              onClick={() => setLineFocus((v) => !v)}
            >
              {lineFocus ? 'Line Focus: On' : 'Line Focus: Off'}
            </button>
            <button
              type="button"
              className={`secondary small ${syllables ? 'active-pill' : ''}`}
              onClick={() => setSyllables((v) => !v)}
            >
              {syllables ? 'Syllables: On' : 'Syllables: Off'}
            </button>
            <button
              type="button"
              className={`secondary small ${prefs.dyslexia ? 'active-pill' : ''}`}
              onClick={() => updatePref('dyslexia', !prefs.dyslexia)}
            >
              {prefs.dyslexia ? 'Dyslexia Font: On' : 'Dyslexia Font: Off'}
            </button>
          </div>
          {lineFocus && (
            <div className="inline small">
              <button
                type="button"
                className="secondary small"
                disabled={activeIndex <= 0}
                onClick={() => setActiveIndex((i) => Math.max(0, i - 1))}
              >
                Previous
              </button>
              <span className="muted">
                {activeIndex + 1} / {content.blocks.length}
              </span>
              <button
                type="button"
                className="secondary small"
                disabled={activeIndex >= content.blocks.length - 1}
                onClick={() => setActiveIndex((i) => Math.min(content.blocks.length - 1, i + 1))}
              >
                Next
              </button>
            </div>
          )}
        </div>

        <div className={`immersive-stage ${lineFocus ? 'line-focus-active' : ''}`}>
          {content.blocks.map((block, idx) => {
            const isFocused = idx === activeIndex
            return (
              <p
                key={idx}
                className={`immersive-paragraph ${isFocused ? 'focused' : ''}`}
                onClick={() => setActiveIndex(idx)}
              >
                {formatSyllables(block)}
              </p>
            )
          })}
        </div>
      </div>
    </Modal>
  )
}
