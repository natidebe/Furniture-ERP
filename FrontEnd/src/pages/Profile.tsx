import { useState } from 'react'
import { api } from '../api/client'
import { useAction, useLocations, usePermissions } from '../api/hooks'
import { useAuth } from '../auth/AuthContext'
import { ConfirmDialog } from '../components/Dialog'
import { Banner, Card, PageHeader } from '../components/ui'
import { formatBoth } from '../lib/ethiopian'
import { ROLE_LABEL } from '../lib/labels'

// P-03 My profile & Telegram link: an 8-character code, sent to the bot as /start CODE within
// 10 minutes. Unlink if a phone is lost.
export default function Profile() {
  const { user, refreshMe } = useAuth()
  const { data: locations } = useLocations()
  const { data: permissions } = usePermissions()
  const [code, setCode] = useState<{ code: string; expires_at: string } | null>(null)
  const [unlink, setUnlink] = useState(false)
  const [copied, setCopied] = useState(false)
  const getCode = useAction(() => api.post<{ code: string; expires_at: string }>('/auth/telegram/link-code/'), { onSuccess: (c) => setCode(c as { code: string; expires_at: string }) })
  const doUnlink = useAction(() => api.post('/auth/telegram/unlink/'), { success: 'Telegram unlinked.', onSuccess: () => refreshMe() })
  if (!user) return null
  const home = locations?.find((l) => l.id === user.home_location)
  const mine = permissions?.filter((p) => user.role === 'admin' || user.permissions.includes(p.codename)) ?? []

  return (
    <main className="page" style={{ maxWidth: 980 }}>
      <PageHeader title="My profile" />
      <div className="grid-cards" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(380px, 100%), 1fr))' }}>
        <Card title="You">
          <dl className="dl">
            <dt>Name</dt><dd style={{ fontWeight: 600 }}>{user.name || '—'}</dd>
            <dt>Username</dt><dd className="mono">{user.username}</dd>
            <dt>Role</dt><dd>{ROLE_LABEL[user.role ?? ''] ?? user.role}</dd>
            <dt>Works at</dt><dd>{home?.name ?? (user.role === 'admin' ? 'Anywhere' : 'Office')}</dd>
          </dl>
          <span className="sub">To change your name, phone or password, ask the admin.</span>
        </Card>
        <Card title="Telegram" actions={<span className={user.telegram_linked ? 'chip c-green' : 'chip c-grey'}>{user.telegram_linked ? 'Linked' : 'Not linked'}</span>}>
          <span className="muted">Telegram brings you alerts{user.role === 'storekeeper' ? ' and lets you release stock from your phone' : ''}. New sales and payments are entered on the web.</span>
          {!user.telegram_linked && !code && <div><button type="button" className="btn btn-pri" onClick={() => getCode.mutate(undefined)} disabled={getCode.isPending}>Get link code</button></div>}
          {code && (
            <div className="stack" style={{ gap: 10, padding: 16, background: 'var(--ground)', borderRadius: 8 }}>
              <span className="lbl">Your link code</span>
              <div className="row">
                <span className="mono" style={{ fontSize: 34, fontWeight: 600, letterSpacing: '.12em' }}>{code.code}</span>
                <button type="button" className="btn btn-sec btn-sm" onClick={() => { navigator.clipboard?.writeText(`/start ${code.code}`).then(() => setCopied(true)).catch(() => {}) }}>{copied ? 'Copied' : 'Copy'}</button>
              </div>
              <span>Send <span className="mono" style={{ fontWeight: 600 }}>/start {code.code}</span> to the company bot within 10 minutes.</span>
              <span className="sub">Expires {formatBoth(code.expires_at)}.</span>
              <div className="row"><button type="button" className="btn btn-sec btn-sm" onClick={() => refreshMe()}>I've sent it — check</button><button type="button" className="btn btn-q btn-sm" onClick={() => getCode.mutate(undefined)}>New code</button></div>
            </div>
          )}
          {user.telegram_linked && <div><button type="button" className="btn btn-dan" onClick={() => setUnlink(true)}>Unlink (lost phone)</button></div>}
        </Card>
      </div>
      <Card title="What you can do">
        {user.role === 'admin' && <Banner kind="info">Admins have every permission.</Banner>}
        {mine.length === 0 ? <span className="muted">No extra permissions — your role's normal work only.</span> : (
          <ul style={{ margin: 0, paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 6 }}>
            {mine.map((p) => <li key={p.codename}>{p.label}</li>)}
          </ul>
        )}
      </Card>
      {unlink && <ConfirmDialog title="Unlink Telegram" danger message="Unlink your Telegram account? The bot stops sending you alerts until you link again." confirmLabel="Unlink" onConfirm={() => doUnlink.mutateAsync(undefined)} onClose={() => setUnlink(false)} />}
    </main>
  )
}
