import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import { useAction, useApi, usePaymentAccounts } from '../../api/hooks'
import type { Order, Paginated, Payment } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { ConfirmDialog, Dialog, ReasonDialog } from '../../components/Dialog'
import { MoneyInput } from '../../components/inputs'
import { Banner, Card, DocLink, Empty, ErrorBanner, EthDate, Field, KindBadge, Loading, Money, PageHeader, StatusChip } from '../../components/ui'
import { money, toCents } from '../../lib/format'
import { label } from '../../lib/labels'

type D = 'verify' | 'reject' | 'reverse' | 'correct' | 'allocate' | 'oldest' | null

// P-53 Payment detail: what was recorded, its allocations (active and released, with why) and
// its permanent history. Corrections reverse the old payment and link the new one.
export default function PaymentDetail() {
  const { id } = useParams()
  const { can, is } = useAuth()
  const q = useApi<Payment>(`/payments/${id}/`)
  const [dialog, setDialog] = useState<D>(null)
  const act = useAction(({ path, body }: { path: string; body?: unknown }) => api.post(`/payments/${id}/${path}/`, body ?? {}), { toastErrors: false, success: 'Done.' })

  if (q.isLoading) return <main className="page"><Loading /></main>
  if (q.error || !q.data) return <main className="page"><ErrorBanner error={q.error} /></main>
  const p = q.data
  const x = p as Payment & { verified_by_name?: string | null; closed_by_name?: string | null; replaces_id?: number | null; replaced_by_id?: number | null }
  const stands = p.status === 'unverified' || p.status === 'verified'
  const unallocated = Number(p.unallocated ?? 0)

  return (
    <main className="page">
      <Link to="/payments" style={{ fontSize: 14 }}>← Payments</Link>
      <PageHeader
        title={<span className="row" style={{ gap: 12 }}><span className="mono">{p.number}</span><StatusChip kind="payment" value={p.status} /><KindBadge kind={p.account_kind} /></span>}
        sub={<>{p.customer_name} · <EthDate value={p.paid_at} /></>}
        actions={<>
          {p.status === 'unverified' && can('verify_payments') && <button type="button" className="btn btn-dan" onClick={() => setDialog('reject')}>Reject…</button>}
          {stands && can('correct_payments') && <button type="button" className="btn btn-dan" onClick={() => setDialog('reverse')}>Reverse…</button>}
          {stands && can('correct_payments') && <button type="button" className="btn btn-sec" onClick={() => setDialog('correct')}>Correct…</button>}
          {stands && unallocated > 0 && is('accountant', 'admin') && <button type="button" className="btn btn-sec" onClick={() => setDialog('oldest')}>Pay oldest first</button>}
          {stands && unallocated > 0 && is('accountant', 'admin') && <button type="button" className="btn btn-sec" onClick={() => setDialog('allocate')}>Allocate advance</button>}
          {p.status === 'unverified' && can('verify_payments') && <button type="button" className="btn btn-pri" onClick={() => setDialog('verify')}>Verify</button>}
        </>} />
      {p.replaces && <Banner kind="info"><span>Corrects <DocLink number={p.replaces} to={x.replaces_id ? `/payments/${x.replaces_id}` : undefined} />.</span></Banner>}
      {p.replaced_by && <Banner kind="warn"><span>Corrected by <DocLink number={p.replaced_by} to={x.replaced_by_id ? `/payments/${x.replaced_by_id}` : undefined} />.</span></Banner>}
      {p.hidden && <Banner kind="info">Personal-account amounts are hidden for you.</Banner>}
      <div className="grid-cards" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(380px, 100%), 1fr))' }}>
        <Card title="Payment">
          <dl className="dl">
            <dt>Amount</dt><dd style={{ fontSize: 20, fontWeight: 700 }}><Money value={p.amount} hidden={p.hidden} unit /></dd>
            <dt>Account</dt><dd className="row" style={{ gap: 6 }}><KindBadge kind={p.account_kind} />{p.account_name ?? '—'}</dd>
            <dt>Method</dt><dd>{label(p.method)}</dd>
            <dt>Receipt</dt><dd className="mono">{p.receipt_number ?? '—'}</dd>
            <dt>Customer</dt><dd><Link to={`/customers/${p.customer}`}>{p.customer_name}</Link></dd>
            <dt>Not yet allocated</dt><dd><Money value={p.unallocated} hidden={p.hidden} /> {unallocated > 0 && <span className="sub">(the customer's advance)</span>}</dd>
            {p.note && <><dt>Note</dt><dd>{p.note}</dd></>}
          </dl>
        </Card>
        <Card title="History">
          <ol className="timeline">
            <li><div><strong>Recorded</strong> by {p.recorded_by_name}<div className="sub"><EthDate value={p.recorded_at} /></div></div></li>
            {p.verified_at && <li><div><strong>Verified</strong>{x.verified_by_name && ` by ${x.verified_by_name}`}<div className="sub"><EthDate value={p.verified_at} /></div></div></li>}
            {p.closed_at && <li className="bad"><div><strong>{label(p.status)}</strong>{x.closed_by_name && ` by ${x.closed_by_name}`}<div className="sub"><EthDate value={p.closed_at} /></div>{p.close_reason && <div>“{p.close_reason}”</div>}</div></li>}
            {p.replaced_by && <li className="warn"><div><strong>Corrected</strong> by <DocLink number={p.replaced_by} /></div></li>}
          </ol>
        </Card>
      </div>
      <Card title="Allocations">
        {p.allocations.length === 0 ? <Empty title="Not tied to any sale" hint="The whole payment is the customer's advance." /> : (
          <div style={{ overflowX: 'auto' }}>
            <table className="tbl">
              <thead><tr><th>Sale</th><th>Line</th><th className="r">Amount</th><th>State</th></tr></thead>
              <tbody>
                {p.allocations.map((a, i) => (
                  <tr key={i} className={a.is_active ? undefined : 'dim'}>
                    <td><DocLink number={a.order_number} to={`/sales/${a.order}`} /></td>
                    <td>{a.product_code ? <span className="mono">{a.product_code}</span> : 'Whole sale'}</td>
                    <td className="r"><Money value={a.amount} hidden={p.hidden} /></td>
                    <td>{a.is_active ? 'Active' : <>Released{a.deactivated_reason && <span className="sub"> — {a.deactivated_reason}</span>}</>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      {dialog === 'verify' && <ConfirmDialog title="Verify payment" message={<>Verify <span className="mono">{p.number}</span>: <strong>{money(p.amount)} ETB</strong> into {p.account_name}?</>} confirmLabel="Verify" onConfirm={() => act.mutateAsync({ path: 'verify' })} onClose={() => setDialog(null)} />}
      {dialog === 'reject' && <ReasonDialog title="Reject payment" placeholder="e.g. Not on the bank statement" message={<>Reject <span className="mono">{p.number}</span>? It no longer counts as paid.</>} confirmLabel="Reject payment" onConfirm={(reason) => act.mutateAsync({ path: 'reject', body: { reason } })} onClose={() => setDialog(null)} />}
      {dialog === 'reverse' && <ReasonDialog title="Reverse payment" message={<>Reverse <span className="mono">{p.number}</span> ({money(p.amount)} ETB)? It stays in the history, no longer counts, and its sales owe the amount again.</>} confirmLabel="Reverse payment" onConfirm={(reason) => act.mutateAsync({ path: 'reverse', body: { reason } })} onClose={() => setDialog(null)} />}
      {dialog === 'oldest' && <ConfirmDialog title="Pay oldest first" message={<>Allocate the {money(p.unallocated)} ETB advance to {p.customer_name}'s oldest unpaid sales first?</>} confirmLabel="Allocate" onConfirm={() => act.mutateAsync({ path: 'allocate-oldest-first' })} onClose={() => setDialog(null)} />}
      {dialog === 'correct' && <CorrectDialog payment={p} onClose={() => setDialog(null)} />}
      {dialog === 'allocate' && <AllocateDialog payment={p} onClose={() => setDialog(null)} />}
    </main>
  )
}

/** Correct: re-record with a new amount, account, method, date or receipt; the old one is reversed and linked. */
function CorrectDialog({ payment, onClose }: { payment: Payment; onClose: () => void }) {
  const navigate = useNavigate()
  const { data: accounts } = usePaymentAccounts()
  const [form, setForm] = useState({ amount: payment.amount ?? '', account: String(payment.account ?? ''), method: payment.method, receipt: payment.receipt_number ?? '', reason: '' })
  const [error, setError] = useState<unknown>(null)
  const account = accounts?.find((a) => String(a.id) === form.account)
  const save = useAction(() => api.post<Payment>(`/payments/${payment.id}/correct/`, {
    reason: form.reason, amount: form.amount, account: Number(form.account), method: form.method,
    receipt_number: account?.kind === 'organization' ? form.receipt || null : null,
  }), { success: (p) => `Corrected — new payment ${(p as Payment).number}.`, onSuccess: (p) => { onClose(); navigate(`/payments/${(p as Payment).id}`) }, toastErrors: false })
  return (
    <Dialog title={`Correct ${payment.number}`} onClose={onClose} wide footer={<>
      <button type="button" className="btn btn-sec" onClick={onClose}>Cancel</button>
      <button type="button" className="btn btn-dan" disabled={!form.reason.trim() || save.isPending} onClick={() => save.mutateAsync(undefined).catch(setError)}>Reverse and re-record</button>
    </>}>
      <span className="muted">The old payment is reversed and kept in the history; a new one is recorded with these details and linked to it.</span>
      <div className="form-grid">
        <Field label="Amount">{(id) => <MoneyInput id={id} value={form.amount} onChange={(v) => setForm({ ...form, amount: v })} />}</Field>
        <Field label="Account">{(id) => (
          <select id={id} className="inp" value={form.account} onChange={(e) => setForm({ ...form, account: e.target.value })}>
            {accounts?.map((a) => <option key={a.id} value={a.id}>{a.name} ({label(a.kind)})</option>)}
          </select>
        )}</Field>
        <Field label="Method">{(id) => (
          <select id={id} className="inp" value={form.method} onChange={(e) => setForm({ ...form, method: e.target.value })}>
            <option value="bank">Bank transfer</option><option value="cash">Cash</option><option value="mobile_money">Mobile money</option>
          </select>
        )}</Field>
        {account?.kind === 'organization' && <Field label="Receipt number">{(id) => <input id={id} className="inp mono" value={form.receipt} onChange={(e) => setForm({ ...form, receipt: e.target.value })} />}</Field>}
      </div>
      <Field label="Reason (required)">{(id) => <input id={id} className="inp" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} placeholder="e.g. Wrong amount typed: 5,000 not 50,000" />}</Field>
      {Boolean(error) && <ErrorBanner error={error} />}
    </Dialog>
  )
}

/** Allocate the advance to specific sales. */
function AllocateDialog({ payment, onClose }: { payment: Payment; onClose: () => void }) {
  const owing = useApi<Paginated<Order>>('/orders/', { customer: payment.customer, owing: 'true', ordering: 'confirmed_at', page_size: 50 })
  const [amounts, setAmounts] = useState<Record<number, string>>({})
  const [error, setError] = useState<unknown>(null)
  const total = Object.values(amounts).reduce((s, v) => s + toCents(v), 0)
  const save = useAction(() => api.post(`/payments/${payment.id}/allocate/`, {
    allocations: Object.entries(amounts).filter(([, v]) => toCents(v) > 0).map(([order, amount]) => ({ order: Number(order), amount })),
  }), { success: 'Allocated.', onSuccess: onClose, toastErrors: false })
  return (
    <Dialog title="Allocate advance" onClose={onClose} wide footer={<>
      <button type="button" className="btn btn-sec" onClick={onClose}>Cancel</button>
      <button type="button" className="btn btn-pri" disabled={total <= 0 || total > toCents(payment.unallocated) || save.isPending} onClick={() => save.mutateAsync(undefined).catch(setError)}>Allocate {money(total / 100)}</button>
    </>}>
      <span className="muted">{money(payment.unallocated)} ETB is not yet tied to a sale.</span>
      {owing.data?.results.length === 0 ? <Empty title="No sales waiting for payment" /> : (
        <table className="tbl tbl-cmp">
          <tbody>
            {owing.data?.results.map((o) => (
              <tr key={o.id}>
                <td><DocLink number={o.number} to={`/sales/${o.id}`} /></td>
                <td className="sub">{o.created_at_ec.split(' (')[0]}</td>
                <td className="r num">remaining {money(o.remaining)}</td>
                <td style={{ width: 170 }}><MoneyInput value={amounts[o.id] ?? ''} onChange={(v) => setAmounts({ ...amounts, [o.id]: v })} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {total > toCents(payment.unallocated) && <span className="fld-err">More than the advance.</span>}
      {Boolean(error) && <ErrorBanner error={error} />}
    </Dialog>
  )
}
