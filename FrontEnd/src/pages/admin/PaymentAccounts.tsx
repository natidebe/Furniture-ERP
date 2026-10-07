import { useState } from 'react'
import { ApiError, api } from '../../api/client'
import { useAction, usePaymentAccounts } from '../../api/hooks'
import type { PaymentAccount } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { Dialog } from '../../components/Dialog'
import { Banner, Empty, ErrorBanner, Field, KindBadge, Loading, PageHeader, StatusChip } from '../../components/ui'
import { label } from '../../lib/labels'

// P-82 Payment accounts (admin edits; others read). Organization vs Personal is the line that
// must never blur (D3). Salespeople only see the accounts they're allowed (set on the user).
export default function PaymentAccounts() {
  const { is } = useAuth()
  const q = usePaymentAccounts()
  const [editing, setEditing] = useState<PaymentAccount | 'new' | null>(null)
  return (
    <main className="page">
      <PageHeader title="Payment accounts" sub={is('salesperson') ? 'The accounts you may record payments into' : 'Where customers pay'}
        actions={is('admin') && <button type="button" className="btn btn-pri" onClick={() => setEditing('new')}>New account</button>} />
      {is('admin') && <Banner kind="info">Enter the real accounts once the system is live (Q8). Then tick, per salesperson, which accounts they may use (Users & permissions).</Banner>}
      {q.isLoading ? <Loading /> : q.data?.length === 0 ? <div className="card"><Empty title="No payment accounts yet" /></div> : (
        <div className="tw">
          <table className="tbl">
            <thead><tr><th>Name</th><th>Kind</th><th>Method</th><th>Bank</th><th>Account number</th><th>Owner</th><th>Status</th><th /></tr></thead>
            <tbody>
              {q.data?.map((a) => (
                <tr key={a.id}>
                  <td style={{ fontWeight: 600 }}>{a.name}</td>
                  <td><KindBadge kind={a.kind} /></td>
                  <td>{label(a.method)}</td>
                  <td>{a.bank_name || '—'}</td>
                  <td className="mono">{a.account_number || '—'}</td>
                  <td>{a.owner_name || '—'}</td>
                  <td><StatusChip kind="active" value={String(a.is_active)} /></td>
                  <td className="r">{is('admin') && <button type="button" className="btn btn-sec btn-sm" onClick={() => setEditing(a)}>Edit</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {editing && <AccountDialog account={editing === 'new' ? null : editing} onClose={() => setEditing(null)} />}
    </main>
  )
}

function AccountDialog({ account, onClose }: { account: PaymentAccount | null; onClose: () => void }) {
  const [form, setForm] = useState({
    name: account?.name ?? '', kind: account?.kind ?? 'organization', method: account?.method ?? 'bank', bank_name: account?.bank_name ?? '',
    account_number: account?.account_number ?? '', owner_name: account?.owner_name ?? '', is_active: account?.is_active ?? true,
  })
  const [error, setError] = useState<unknown>(null)
  const save = useAction(() => (account ? api.patch(`/payment-accounts/${account.id}/`, form) : api.post('/payment-accounts/', form)), { success: 'Account saved.', onSuccess: onClose, toastErrors: false })
  const fields = error instanceof ApiError ? error.fields : {}
  return (
    <Dialog title={account ? `Edit ${account.name}` : 'New payment account'} onClose={onClose} footer={<>
      <button type="button" className="btn btn-sec" onClick={onClose}>Cancel</button>
      <button type="button" className="btn btn-pri" disabled={save.isPending || !form.name} onClick={() => save.mutateAsync(undefined).catch(setError)}>Save</button>
    </>}>
      <div className="form-grid">
        <Field label="Name" error={fields.name}>{(id) => <input id={id} className="inp" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. CBE – Company current" />}</Field>
        <Field label="Kind" error={fields.kind}>{(id) => (
          <select id={id} className="inp" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as 'organization' | 'personal' })}>
            <option value="organization">Organization (official receipts)</option><option value="personal">Personal</option>
          </select>
        )}</Field>
        <Field label="Method" error={fields.method}>{(id) => (
          <select id={id} className="inp" value={form.method} onChange={(e) => setForm({ ...form, method: e.target.value as 'bank' })}>
            <option value="bank">Bank</option><option value="cash">Cash</option><option value="mobile_money">Mobile money</option>
          </select>
        )}</Field>
        <Field label="Bank name" error={fields.bank_name}>{(id) => <input id={id} className="inp" value={form.bank_name} onChange={(e) => setForm({ ...form, bank_name: e.target.value })} />}</Field>
        <Field label="Account number" error={fields.account_number}>{(id) => <input id={id} className="inp mono" value={form.account_number} onChange={(e) => setForm({ ...form, account_number: e.target.value })} />}</Field>
        <Field label="Owner name" error={fields.owner_name}>{(id) => <input id={id} className="inp" value={form.owner_name} onChange={(e) => setForm({ ...form, owner_name: e.target.value })} />}</Field>
      </div>
      <label className="check"><input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />Active</label>
      {Boolean(error) && !Object.keys(fields).length && <ErrorBanner error={error} />}
    </Dialog>
  )
}
