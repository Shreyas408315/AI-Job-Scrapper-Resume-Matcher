import { useEffect, useState } from 'react'
import { Link, Navigate, Route, Routes, useNavigate, useParams } from 'react-router-dom'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function apiRequest(path, options = {}) {
  const token = localStorage.getItem('access_token')
  const headers = new Headers(options.headers || {})
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`${API_URL}${path}`, { ...options, headers })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body.detail || 'Something went wrong')
  return body
}

function Shell({ children }) {
  const navigate = useNavigate()
  function logout() { localStorage.removeItem('access_token'); navigate('/login') }
  return <div className="app-shell"><header className="topbar"><Link className="brand" to="/dashboard"><span>◎</span> Matchwork</Link>{localStorage.getItem('access_token') && <nav><Link to="/upload">Resume</Link><Link to="/dashboard">Matches</Link><button className="text-button" onClick={logout}>Log out</button></nav>}</header><main>{children}</main></div>
}

function AuthPage() {
  const navigate = useNavigate(); const [mode, setMode] = useState('login'); const [email, setEmail] = useState(''); const [password, setPassword] = useState(''); const [error, setError] = useState(''); const [busy, setBusy] = useState(false)
  async function submit(event) { event.preventDefault(); setBusy(true); setError(''); try { const data = await apiRequest(`/api/auth/${mode}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) }); localStorage.setItem('access_token', data.access_token); navigate('/upload') } catch (err) { setError(err.message) } finally { setBusy(false) } }
  return <section className="auth-layout"><div className="intro-panel"><p className="eyebrow">CAREER SIGNAL, CLARIFIED</p><h1>Find the roles that fit the work you already do.</h1><p>Upload a resume, pull fresh jobs, and get a ranked read on where your experience lands strongest.</p><div className="signal-row"><strong>semantic</strong><span>resume ↔ opportunity</span></div></div><form className="form-panel" onSubmit={submit}><p className="eyebrow">YOUR WORKSPACE</p><h2>{mode === 'login' ? 'Welcome back' : 'Create your workspace'}</h2><p className="muted">One account. One focused job search.</p><label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label><label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} minLength="8" required /></label>{error && <p className="error">{error}</p>}<button className="primary-button" disabled={busy}>{busy ? 'Working...' : mode === 'login' ? 'Sign in' : 'Create account'}</button><button type="button" className="switch-button" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}>{mode === 'login' ? 'Need an account? Register' : 'Already have an account? Sign in'}</button></form></section>
}

function UploadPage() {
  const navigate = useNavigate(); const [file, setFile] = useState(null); const [resumes, setResumes] = useState([]); const [error, setError] = useState(''); const [busy, setBusy] = useState(false)
  useEffect(() => { apiRequest('/api/resumes/me').then(setResumes).catch((err) => setError(err.message)) }, [])
  async function upload(event) { event.preventDefault(); if (!file) return setError('Choose a PDF or DOCX resume first.'); if (file.size > 5 * 1024 * 1024) return setError('Resume must be smaller than 5 MB.'); setBusy(true); setError(''); const form = new FormData(); form.append('file', file); try { const resume = await apiRequest('/api/resumes/upload', { method: 'POST', body: form }); setResumes((current) => [resume, ...current]); navigate('/dashboard') } catch (err) { setError(err.message) } finally { setBusy(false) } }
  return <section className="page-section"><div className="section-heading"><div><p className="eyebrow">STEP 01 / SOURCE</p><h1>Bring your experience.</h1><p className="lede">Your resume becomes the lens for every match. We keep the text private and only return useful metadata here.</p></div><span className="step-mark">01</span></div><form className="upload-zone" onSubmit={upload}><label className="file-picker"><span className="upload-icon">↑</span><strong>{file ? file.name : 'Drop your resume here'}</strong><small>PDF or DOCX · up to 5 MB</small><input type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => { setFile(event.target.files[0]); setError('') }} /></label>{error && <p className="error">{error}</p>}<button className="primary-button" disabled={busy}>{busy ? 'Extracting and embedding...' : 'Upload resume'}</button></form>{resumes.length > 0 && <div className="resume-list"><p className="eyebrow">SAVED RESUMES</p>{resumes.map((resume) => <div className="resume-row" key={resume.id}><span className="file-dot">{resume.file_type.toUpperCase()}</span><div><strong>{resume.filename}</strong><small>{resume.has_embedding ? 'Ready for matching' : 'Processing'}</small></div><button className="secondary-button" onClick={() => navigate('/dashboard')}>Use resume</button></div>)}</div>}</section>
}

function Dashboard() {
  const [resumes, setResumes] = useState([]); const [matches, setMatches] = useState(null); const [board, setBoard] = useState('airbnb'); const [error, setError] = useState(''); const [busy, setBusy] = useState('')
  async function loadMatches(resumeId) { setBusy('match'); try { setMatches(await apiRequest(`/api/matches/${resumeId}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ top_n: 10 }) })) } catch (err) { setError(err.message) } finally { setBusy('') } }
  useEffect(() => { apiRequest('/api/resumes/me').then((data) => { setResumes(data); if (data[0]?.has_embedding) loadMatches(data[0].id) }).catch((err) => setError(err.message)) }, [])
  async function syncJobs() { setBusy('sync'); setError(''); try { await apiRequest(`/api/jobs/sync/${board}`, { method: 'POST' }); if (resumes[0]) await loadMatches(resumes[0].id) } catch (err) { setError(err.message) } finally { setBusy('') } }
  if (!resumes.length) return <section className="empty-state"><span className="step-mark">01</span><p className="eyebrow">YOUR DASHBOARD</p><h1>Start with a resume.</h1><p>Once we have your experience, we can show you where it travels.</p><Link className="primary-button inline-button" to="/upload">Upload resume</Link></section>
  return <section className="page-section"><div className="dashboard-head"><div><p className="eyebrow">STEP 02 / SIGNAL</p><h1>Your opportunity map.</h1><p className="lede">Ranked by semantic similarity, then ready for a deeper explanation.</p></div><div className="sync-control"><label>Source<select value={board} onChange={(event) => setBoard(event.target.value)}><option value="airbnb">Airbnb</option><option value="spotify">Spotify</option><option value="figma">Figma</option><option value="cloudflare">Cloudflare</option></select></label><button className="secondary-button" onClick={syncJobs} disabled={busy}>{busy === 'sync' ? 'Syncing...' : 'Sync jobs'}</button></div></div>{error && <p className="error">{error}</p>}{busy === 'match' && <p className="status-line">Comparing your resume with available roles...</p>}{matches?.matches?.length ? <div className="match-list">{matches.matches.map((match, index) => <Link className="match-row" to={`/matches/${match.id}`} key={match.id}><span className="rank">{String(index + 1).padStart(2, '0')}</span><div className="match-main"><strong>{match.job_title}</strong><span>{match.company} · {match.location || 'Location flexible'}</span></div><div className="score"><strong>{Math.round(match.similarity_score * 100)}%</strong><small>match</small></div><span className="arrow">↗</span></Link>)}</div> : <div className="empty-results"><p className="eyebrow">NO MATCHES YET</p><h2>Sync a job source to begin.</h2><p>We will fetch structured postings and compare them with your latest resume.</p><button className="primary-button" onClick={syncJobs} disabled={busy}>{busy === 'sync' ? 'Syncing...' : `Sync ${board} jobs`}</button></div>}</section>
}

function DetailPage() {
  const { matchId } = useParams()
  const [match, setMatch] = useState(null)
  const [explanation, setExplanation] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('loading')

  useEffect(() => {
    apiRequest(`/api/matches/detail/${matchId}`)
      .then((data) => { setMatch(data); setExplanation(data.llm_explanation) })
      .catch((err) => setError(err.message))
      .finally(() => setBusy(''))
  }, [matchId])

  async function explain() {
    setBusy('explain')
    setError('')
    try {
      setExplanation(await apiRequest(`/api/matches/detail/${matchId}/explain`, { method: 'POST' }))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  if (busy === 'loading') return <section className="empty-state"><p className="status-line">Loading job details...</p></section>
  if (!match) return <section className="empty-state"><p className="error">{error || 'Match not found.'}</p><Link className="primary-button inline-button" to="/dashboard">Back to matches</Link></section>

  return <section className="page-section detail-page">
    <Link className="back-link" to="/dashboard">← Back to matches</Link>
    <div className="detail-heading"><div><p className="eyebrow">MATCH DETAIL</p><h1>{match.job_title}</h1><p className="detail-company">{match.company} · {match.location || 'Location flexible'}</p></div><strong className="detail-score">{Math.round(match.similarity_score * 100)}%<small> match</small></strong></div>
    <div className="job-description"><div className="job-description-head"><p className="eyebrow">JOB DESCRIPTION</p><a href={match.job_url} target="_blank" rel="noreferrer">View original ↗</a></div><p>{match.job_description}</p></div>
    <div className="explain-panel">{!explanation ? <><div><span className="orb">✦</span><h2>Ready for a closer read?</h2><p>The analysis returns reasoning, missing skills, and concrete resume edits.</p></div><button className="primary-button" onClick={explain} disabled={busy}>{busy === 'explain' ? 'Analyzing...' : 'Generate explanation'}</button></> : <><p className="eyebrow">MODEL READ</p><h2>{explanation.match_score_reasoning}</h2><div className="detail-grid"><div><p className="eyebrow">MISSING SKILLS</p>{explanation.missing_skills.length ? <ul>{explanation.missing_skills.map((skill) => <li key={skill}>{skill}</li>)}</ul> : <p>No clear gaps found.</p>}</div><div><p className="eyebrow">RESUME IMPROVEMENTS</p><ul>{explanation.resume_improvement_tips.map((tip) => <li key={tip}>{tip}</li>)}</ul></div></div></>}</div>{error && <p className="error">{error}</p>}
  </section>
}

function Protected({ children }) { return localStorage.getItem('access_token') ? children : <Navigate to="/login" replace /> }
function App() { return <Shell><Routes><Route path="/login" element={<AuthPage />} /><Route path="/upload" element={<Protected><UploadPage /></Protected>} /><Route path="/dashboard" element={<Protected><Dashboard /></Protected>} /><Route path="/matches/:matchId" element={<Protected><DetailPage /></Protected>} /><Route path="*" element={<Navigate to={localStorage.getItem('access_token') ? '/dashboard' : '/login'} replace />} /></Routes></Shell> }

export default App
