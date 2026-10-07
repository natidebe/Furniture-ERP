import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Field } from '../components/ui'

// P-01. Wrong password → 401; after 5 failures the account is locked for 30 minutes →
// 403 {"code": "account_locked"}.
export default function Login() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<'wrong' | 'locked' | 'other' | null>(null)
  const [otherText, setOtherText] = useState('')

  const from = (location.state as { from?: string } | null)?.from ?? '/'
  if (user) return <Navigate to={from} replace />

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setProblem(null)
    try {
      await login(username.trim(), password)
      navigate(from, { replace: true })
    } catch (err) {
      if (err instanceof ApiError && err.code === 'account_locked') setProblem('locked')
      else if (err instanceof ApiError && (err.status === 401 || err.status === 400)) setProblem('wrong')
      else {
        setProblem('other')
        setOtherText(err instanceof TypeError ? 'Cannot reach the server. Check the connection.' : 'Could not log in. Try again.')
      }
      setBusy(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', minHeight: '100vh' }}>
      <div style={{ flex: '1 1 480px', background: 'var(--sidebar)', color: 'var(--sidebar-text)', padding: 56, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: 48 }}>
        <div className="row" style={{ gap: 12 }}>
          <span className="brand-mark" style={{ width: 44, height: 44, fontSize: 18 }}>F</span>
          <span style={{ fontWeight: 600, fontSize: 18, color: '#fff' }}>Furniture ERP</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 460 }}>
          <h1 style={{ fontSize: 40, lineHeight: 1.15, color: '#fff' }}>Stock, sales and payments for every branch.</h1>
          <div style={{ display: 'flex', flexDirection: 'column', fontSize: 15 }}>
            {[['Piassa', 'PIA · PIA-UG'], ['Denbel', 'DEN'], ['Pawlos warehouse', 'PAW']].map(([name, code], i) => (
              <div key={name} className="spread" style={{ padding: '12px 0', borderBottom: i < 2 ? '1px solid var(--sidebar-line)' : 0 }}>
                <span>{name}</span><span className="mono" style={{ color: 'var(--sidebar-muted)' }}>{code}</span>
              </div>
            ))}
          </div>
        </div>
        <span style={{ fontSize: 13, color: 'var(--sidebar-muted)' }}>Problems signing in? Ask the admin to reset your password.</span>
      </div>

      <div style={{ flex: '1 1 480px', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '56px 24px' }}>
        <form onSubmit={submit} style={{ width: '100%', maxWidth: 380, display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div className="stack" style={{ gap: 6 }}>
            <h2 style={{ fontSize: 28 }}>Log in</h2>
            <p className="muted">Use the username the admin gave you.</p>
          </div>
          {problem === 'wrong' && <div role="alert" className="alert alert-err">Wrong username or password.</div>}
          {problem === 'locked' && <div role="alert" className="alert alert-warn">Too many failed attempts. Try again in 30 minutes.</div>}
          {problem === 'other' && <div role="alert" className="alert alert-err">{otherText}</div>}
          <Field label="Username">
            {(id) => <input id={id} className="inp" style={{ height: 48, fontSize: 15 }} autoComplete="username" required value={username} onChange={(e) => setUsername(e.target.value)} />}
          </Field>
          <Field label="Password">
            {(id) => (
              <div className="row" style={{ flexWrap: 'nowrap', gap: 8 }}>
                <input id={id} className="inp" style={{ height: 48, fontSize: 15 }} type={show ? 'text' : 'password'} autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
                <button type="button" className="btn btn-sec" style={{ height: 48, minWidth: 72 }} onClick={() => setShow(!show)}>{show ? 'Hide' : 'Show'}</button>
              </div>
            )}
          </Field>
          <button type="submit" className="btn btn-pri btn-lg" disabled={busy}>{busy ? 'Logging in…' : 'Log in'}</button>
          <p className="sub" style={{ fontSize: 13 }}>You stay signed in for 7 days on this computer unless you log out.</p>
        </form>
      </div>
    </div>
  )
}
