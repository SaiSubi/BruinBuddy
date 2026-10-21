import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { api, setOnExpired } from './api.js'
import { getToken, initAuth, signOut } from './auth.js'
import { navigate, takeQueryParams, useRoute } from './router.js'
import { Banner, Loading } from './ui.jsx'
import AuthScreen from './AuthScreen.jsx'
import TopBar from './TopBar.jsx'
import Welcome from './Welcome.jsx'
import CreateCourse from './CreateCourse.jsx'
import CourseHome from './CourseHome.jsx'
import ChatView from './ChatView.jsx'
const StaffConsole = lazy(() => import('./staff/StaffConsole.jsx')) // students never load the staff screens
import About from './About.jsx'

const LAST_COURSE = 'bb_last_course'
const remember = (id) => { try { localStorage.setItem(LAST_COURSE, String(id)) } catch { /* ignore */ } }
const recalled = () => { try { return Number(localStorage.getItem(LAST_COURSE)) } catch { return 0 } }

export default function App() {
  const [cfg, setCfg] = useState(null)
  const [bootError, setBootError] = useState(null)
  const [me, setMe] = useState(undefined) // undefined: loading, null: signed out
  const [params, setParams] = useState(takeQueryParams) // one-time ?checkout=…, ?reset=1 or a sign-in error
  const [notice, setNotice] = useState(() => params.error_description || '')
  const signedIn = useRef(false)
  const route = useRoute()

  const loadMe = useCallback(async () => {
    if (!(await getToken())) { setMe(null); return null }
    try {
      const m = await api.me()
      signedIn.current = true
      setMe(m)
      return m
    } catch (e) {
      if (e.status !== 401) setNotice(e.message)
      setMe(null)
      return null
    }
  }, [])

  useEffect(() => {
    setOnExpired(() => {
      if (signedIn.current) setNotice('Your session has expired. Please log in again.')
      signedIn.current = false
      signOut()
      setMe(null)
    })
    ;(async () => {
      try {
        const c = await api.config()
        await initAuth(c)
        setCfg(c)
        await loadMe()
      } catch (e) {
        setBootError(e)
      }
    })()
  }, [loadMe])

  const logOut = async () => {
    signedIn.current = false
    await signOut()
    setMe(null)
    setNotice('')
    navigate('/')
  }

  if (bootError) {
    return (
      <main className="signin">
        <div className="card">
          <h1>BruinBuddy</h1>
          <Banner kind="error">{bootError.message || 'BruinBuddy is unavailable right now.'}</Banner>
          <button className="primary" onClick={() => window.location.reload()}>Try again</button>
        </div>
      </main>
    )
  }
  if (!cfg || me === undefined) return <Loading />

  if (params.reset && me) {
    return <AuthScreen cfg={cfg} initialMode="reset" onDone={() => { setParams({}); navigate('/') }} />
  }
  if (!me) {
    if (route[0] === 'about') return <About onBack={() => navigate('/')} />
    return <AuthScreen cfg={cfg} notice={notice} onSignedIn={async () => { setNotice(''); await loadMe() }} />
  }

  const shell = (content, wide = false) => (
    <div className="page">
      <TopBar me={me} courseId={route[0] === 'c' ? Number(route[1]) : null} onLogOut={logOut} />
      <main className={wide ? 'content wide' : 'content'}>{content}</main>
    </div>
  )

  if (params.checkout && params.course) {
    return shell(<CheckoutReturn params={params} onDone={async (path) => { setParams({}); await loadMe(); navigate(path) }} />)
  }

  const [section, id, ...rest] = route
  if (section === 'about') return shell(<About onBack={() => window.history.back()} />)
  if (section === 'join') return shell(<Welcome me={me} onJoined={loadMe} />)
  if (section === 'create') return shell(<CreateCourse cfg={cfg} />)
  if (section === 'c' && id) {
    remember(id)
    return <CourseRoute key={id} id={Number(id)} rest={rest} me={me} cfg={cfg} onLogOut={logOut} reloadMe={loadMe} />
  }
  if (!me.courses.length) return shell(<Welcome me={me} onJoined={loadMe} />)
  const last = me.courses.find((c) => c.id === recalled()) || me.courses[0]
  navigate(`/c/${last.id}`)
  return <Loading />
}

function CheckoutReturn({ params, onDone }) {
  const [status, setStatus] = useState(params.checkout === 'success' ? 'Confirming your payment…' : '')
  useEffect(() => {
    const id = Number(params.course)
    if (params.checkout !== 'success') { onDone(`/c/${id}`); return }
    let cancelled = false
    ;(async () => {
      for (let i = 0; i < 12 && !cancelled; i++) {
        try {
          const r = await api.confirmCheckout(id, params.session_id)
          if (r.status === 'active') { onDone(`/c/${id}/staff/setup`); return }
        } catch { /* keep polling: the webhook may still arrive */ }
        await new Promise((res) => setTimeout(res, 1500))
      }
      if (!cancelled) setStatus('We haven’t received confirmation from Stripe yet. Your course will activate as soon as it arrives; you can refresh this page in a minute.')
    })()
    return () => { cancelled = true }
  }, [params, onDone])
  return (
    <div className="narrow">
      <h1>Payment</h1>
      <Banner>{status}</Banner>
      <button className="secondary" onClick={() => onDone(`/c/${params.course}`)}>Go to the course</button>
    </div>
  )
}

function CourseRoute({ id, rest, me, cfg, onLogOut, reloadMe }) {
  const [course, setCourse] = useState(null)
  const [error, setError] = useState(null)
  const load = useCallback(async () => {
    try {
      setCourse(await api.course(id))
      setError(null)
    } catch (e) {
      setError(e)
    }
  }, [id])
  useEffect(() => { load() }, [load])

  const top = <TopBar me={me} courseId={id} onLogOut={onLogOut} />
  if (error) {
    return (
      <div className="page">{top}
        <main className="content">
          <div className="narrow">
            <Banner kind="error">{error.status === 404 ? 'This course doesn’t exist or you’re not a member of it.' : error.message}</Banner>
            <button className="secondary" onClick={async () => { await reloadMe(); navigate('/') }}>Go to my courses</button>
          </div>
        </main>
      </div>
    )
  }
  if (!course) return <div className="page">{top}<Loading /></div>

  const staff = course.role === 'owner' || course.role === 'staff'
  const [view, sub] = rest
  if (view === 'chat' && sub) {
    return <div className="page chatpage">{top}<ChatView key={sub} course={course} chatId={Number(sub)} preview={staff} onCourseChange={load} /></div>
  }
  if (staff && view !== 'preview') {
    return (
      <div className="page">{top}
        <main className="content wide">
          <Suspense fallback={<Loading />}>
            <StaffConsole course={course} tab={view === 'staff' ? sub || 'setup' : 'setup'} reload={load} cfg={cfg} />
          </Suspense>
        </main>
      </div>
    )
  }
  return <div className="page">{top}<main className="content"><CourseHome course={course} preview={staff} reload={load} /></main></div>
}
