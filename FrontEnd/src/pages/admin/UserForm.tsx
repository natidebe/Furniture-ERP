import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ApiError, api } from '../../api/client'
import { useAction, useApi, usePaymentAccounts, usePermissions, useRealLocations } from '../../api/hooks'
import type { Permission, Role, User } from '../../api/types'
import { ConfirmDialog } from '../../components/Dialog'
import { Banner, Card, ErrorBanner, Field, KindBadge, Loading, PageHeader } from '../../components/ui'
import { ROLE_LABEL } from '../../lib/labels'

interface Form {
  username: string; full_name: string; phone: string; role: Role; home_location: string; is_active: boolean
  password: string; permissions: Permission[]; allowed_payment_accounts: number[]
}

// P-80 Create / edit a user: role, home location, permissions (checkboxes with their default
// roles), allowed payment accounts (salespeople). Changing the role resets the permissions to
// the role's defaults — the page warns first. Admins have everything.
export default function UserForm() {
  const { id } = useParams()
  const navigate = useNavigate()
  const existing = useApi<User>(id ? `/users/${id}/` : null)
  const { data: permissions } = usePermissions()
  const { data: locations } = useRealLocations()
  const { data: accounts } = usePaymentAccounts()
  const [form, setForm] = useState<Form>({ username: '', full_name: '', phone: '', role: 'salesperson', home_location: '', is_active: true, password: '', permissions: [], allowed_payment_accounts: [] })
  const [error, setError] = useState<unknown>(null)
  const [confirmRole, setConfirmRole] = useState(false)

  useEffect(() => {
    const u = existing.data
    if (u) setForm({ username: u.username, full_name: u.full_name ?? '', phone: u.phone ?? '', role: u.role ?? 'salesperson', home_location: u.home_location ? String(u.home_location) : '', is_active: u.is_active ?? true, password: '', permissions: u.permissions ?? [], allowed_payment_accounts: u.allowed_payment_accounts ?? [] })
  }, [existing.data])
  // A new user starts with the role's defaults (the server applies them too).
  useEffect(() => {
    if (!id && permissions) setForm((f) => ({ ...f, permissions: permissions.filter((p) => p.default_for_roles.includes(f.role)).map((p) => p.codename) }))
  }, [id, permissions, form.role])

  const roleChanged = Boolean(existing.data && existing.data.role !== form.role)
  const set = <K extends keyof Form>(k: K, v: Form[K]) => setForm((f) => ({ ...f, [k]: v }))
  const save = useAction(() => {
    const body: Record<string, unknown> = {
      username: form.username, full_name: form.full_name, phone: form.phone, role: form.role,
      home_location: form.home_location ? Number(form.home_location) : null, is_active: form.is_active,
      allowed_payment_accounts: form.allowed_payment_accounts,
    }
    // After a role change the server resets permissions to the new role's defaults.
    if (!roleChanged) body.permissions = form.permissions
    if (form.password) body.password = form.password
    return id ? api.patch<User>(`/users/${id}/`, body) : api.post<User>('/users/', body)
  }, { success: id ? 'User saved.' : 'User created.', onSuccess: () => navigate('/admin/users'), toastErrors: false })

  const submit = async () => {
    setError(null)
    try { await save.mutateAsync(undefined) } catch (e) { setError(e) }
  }
  if (id && existing.isLoading) return <main className="page"><Loading /></main>
  const fields = error instanceof ApiError ? error.fields : {}
  const needsHome = form.role === 'salesperson' || form.role === 'storekeeper'
  const admin = form.role === 'admin'

  return (
    <main className="page" style={{ maxWidth: 1000 }}>
      <Link to="/admin/users" style={{ fontSize: 14 }}>← Users</Link>
      <PageHeader title={id ? `Edit ${existing.data?.full_name || existing.data?.username}` : 'New user'} />
      <Card title="Account">
        <div className="form-grid">
          <Field label="Username" error={fields.username}>{(fid) => <input id={fid} className="inp mono" value={form.username} onChange={(e) => set('username', e.target.value)} autoComplete="off" />}</Field>
          <Field label="Full name" error={fields.full_name}>{(fid) => <input id={fid} className="inp" value={form.full_name} onChange={(e) => set('full_name', e.target.value)} />}</Field>
          <Field label="Phone" error={fields.phone}>{(fid) => <input id={fid} className="inp" value={form.phone} onChange={(e) => set('phone', e.target.value)} />}</Field>
          <Field label={id ? 'New password (leave empty to keep)' : 'Password'} error={fields.password}>{(fid) => <input id={fid} className="inp" type="password" autoComplete="new-password" value={form.password} onChange={(e) => set('password', e.target.value)} />}</Field>
          <Field label="Role" error={fields.role}>{(fid) => (
            <select id={fid} className="inp" value={form.role} onChange={(e) => set('role', e.target.value as Role)}>
              {Object.entries(ROLE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          )}</Field>
          <Field label="Works at" hint={needsHome ? 'Needed for salespeople and storekeepers' : 'Optional'} error={fields.home_location}>{(fid) => (
            <select id={fid} className="inp" value={form.home_location} onChange={(e) => set('home_location', e.target.value)}>
              <option value="">{needsHome ? 'Choose…' : 'Office / anywhere'}</option>{locations?.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          )}</Field>
        </div>
        <label className="check"><input type="checkbox" checked={form.is_active} onChange={(e) => set('is_active', e.target.checked)} />Active — can log in (deactivate instead of deleting)</label>
      </Card>
      <Card title="Permissions">
        {roleChanged && <Banner kind="warn">Changing the role resets the permissions to the {ROLE_LABEL[form.role]} defaults when you save.</Banner>}
        {admin && <Banner kind="info">Admins have every permission.</Banner>}
        <div className="stack" style={{ gap: 10 }}>
          {permissions?.map((p) => (
            <label key={p.codename} className="check" style={{ alignItems: 'flex-start' }}>
              <input type="checkbox" disabled={admin || roleChanged} checked={admin || form.permissions.includes(p.codename)}
                onChange={(e) => set('permissions', e.target.checked ? [...form.permissions, p.codename] : form.permissions.filter((x) => x !== p.codename))} />
              <span className="stack" style={{ gap: 2 }}><span>{p.label}</span><span className="sub mono">{p.codename} · default for {p.default_for_roles.map((r) => ROLE_LABEL[r]).join(', ')}</span></span>
            </label>
          ))}
        </div>
      </Card>
      {form.role === 'salesperson' && (
        <Card title="Payment accounts this salesperson may use">
          {accounts?.length === 0 && <span className="muted">No payment accounts yet. <Link to="/admin/payment-accounts">Add them first.</Link></span>}
          <div className="stack" style={{ gap: 8 }}>
            {accounts?.map((a) => (
              <label key={a.id} className="check">
                <input type="checkbox" checked={form.allowed_payment_accounts.includes(a.id)}
                  onChange={(e) => set('allowed_payment_accounts', e.target.checked ? [...form.allowed_payment_accounts, a.id] : form.allowed_payment_accounts.filter((x) => x !== a.id))} />
                <KindBadge kind={a.kind} /> {a.name}{!a.is_active && <span className="sub"> (closed)</span>}
              </label>
            ))}
          </div>
        </Card>
      )}
      {Boolean(error) && !Object.keys(fields).length && <ErrorBanner error={error} />}
      <div className="row" style={{ justifyContent: 'flex-end' }}>
        <Link className="btn btn-sec" to="/admin/users">Cancel</Link>
        <button type="button" className="btn btn-pri" disabled={save.isPending || !form.username || (!id && !form.password)} onClick={() => (roleChanged ? setConfirmRole(true) : submit())}>{id ? 'Save changes' : 'Create user'}</button>
      </div>
      {confirmRole && <ConfirmDialog title="Change role" message={<>Change the role from {ROLE_LABEL[existing.data?.role ?? '']} to {ROLE_LABEL[form.role]}? Their permissions are reset to the {ROLE_LABEL[form.role]} defaults. Every change is audited.</>}
        confirmLabel="Change role" onConfirm={submit} onClose={() => setConfirmRole(false)} />}
    </main>
  )
}
