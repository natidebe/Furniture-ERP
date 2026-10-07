import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import { useAction, useApi } from '../../api/hooks'
import type { Paginated, Payment } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { ConfirmDialog, ReasonDialog } from '../../components/Dialog'
import { DocLink, Empty, EthDate, KindBadge, Money, PageHeader, Pager, QueryState } from '../../components/ui'
import { fromCents, money, toCents } from '../../lib/format'
import { useFilters } from '../../lib/useFilters'

// P-52 Payments to verify — oldest first. Verify in one click (or several at once); Reject
// needs a reason ("not on the bank statement").
export default function VerifyPayments() {
  const { can } = useAuth()
  const { page, setPage } = useFilters([] as const)
  const q = useApi<Paginated<Payment>>('/payments/', { status: 'unverified', ordering: 'paid_at', page }, { refetchInterval: 60_000 })
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [dialog, setDialog] = useState<{ kind: 'verify' | 'reject' | 'bulk'; p?: Payment } | null>(null)
  const verify = useAction((id: number) => api.post(`/payments/${id}/verify/`), { toastErrors: false })
  const reject = useAction(({ id, reason }: { id: number; reason: string }) => api.post(`/payments/${id}/reject/`, { reason }), { success: 'Payment rejected.', toastErrors: false })

  if (!can('verify_payments')) return <main className="page"><Empty title="Verifying payments needs the verify_payments permission" /></main>
  const rows = q.data?.results ?? []
  const chosen = rows.filter((p) => selected.has(p.id))
  const bulkTotal = chosen.reduce((s, p) => s + toCents(p.amount), 0)
  const toggle = (id: number) => setSelected((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n })

  return (
    <main className="page">
      <PageHeader title="Payments to verify" sub={q.data ? `${q.data.count} waiting · oldest first` : ' '}
        actions={chosen.length > 0 && <button type="button" className="btn btn-pri" onClick={() => setDialog({ kind: 'bulk' })}>Verify {chosen.length} selected</button>} />
      <div className="tw">
        <QueryState query={q} empty={rows.length === 0} emptyHint="Nothing to verify 👍">
          <table className="tbl">
            <thead><tr>
              <th><input type="checkbox" aria-label="Select all" checked={rows.length > 0 && chosen.length === rows.length} onChange={(e) => setSelected(e.target.checked ? new Set(rows.map((p) => p.id)) : new Set())} /></th>
              <th>Payment</th><th>Paid</th><th className="r">Amount</th><th>Account</th><th>Receipt</th><th>Customer</th><th>For</th><th>Recorded by</th><th />
            </tr></thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.id}>
                  <td><input type="checkbox" aria-label={`Select ${p.number}`} checked={selected.has(p.id)} onChange={() => toggle(p.id)} /></td>
                  <td><DocLink number={p.number} to={`/payments/${p.id}`} strong /></td>
                  <td><EthDate value={p.paid_at} /></td>
                  <td className="r"><Money value={p.amount} hidden={p.hidden} strong /></td>
                  <td><span className="row" style={{ gap: 6, flexWrap: 'nowrap' }}><KindBadge kind={p.account_kind} short />{p.account_name}</span></td>
                  <td className="mono" style={{ fontSize: 13 }}>{p.receipt_number ?? '—'}</td>
                  <td><Link to={`/customers/${p.customer}`} style={{ color: 'var(--ink)' }}>{p.customer_name}</Link></td>
                  <td className="wrap">{p.allocations.filter((a) => a.is_active).map((a) => a.order_number).join(', ') || <span className="muted">Advance</span>}</td>
                  <td>{p.recorded_by_name}</td>
                  <td className="r">
                    <div className="row" style={{ flexWrap: 'nowrap', justifyContent: 'flex-end' }}>
                      <button type="button" className="btn btn-dan btn-sm" onClick={() => setDialog({ kind: 'reject', p })}>Reject…</button>
                      <button type="button" className="btn btn-pri btn-sm" onClick={() => setDialog({ kind: 'verify', p })}>Verify</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </QueryState>
      </div>
      <Pager page={page} count={q.data?.count ?? 0} onPage={setPage} note="Check each payment against the bank or Telebirr statement before verifying." />
      {dialog?.kind === 'verify' && dialog.p && (
        <ConfirmDialog title="Verify payment" message={<>Verify <span className="mono">{dialog.p.number}</span>: <strong>{money(dialog.p.amount)} ETB</strong> into <KindBadge kind={dialog.p.account_kind} /> {dialog.p.account_name}{dialog.p.receipt_number ? `, receipt ${dialog.p.receipt_number}` : ''}, from {dialog.p.customer_name}?</>}
          confirmLabel="Verify" onConfirm={() => verify.mutateAsync(dialog.p!.id)} onClose={() => setDialog(null)} />
      )}
      {dialog?.kind === 'bulk' && (
        <ConfirmDialog title="Verify payments" message={<>Verify <strong>{chosen.length} payments</strong> totalling <strong>{money(fromCents(bulkTotal))} ETB</strong>: {chosen.map((p) => p.number).join(', ')}?</>}
          confirmLabel={`Verify ${chosen.length}`} onConfirm={async () => { for (const p of chosen) await verify.mutateAsync(p.id); setSelected(new Set()) }} onClose={() => setDialog(null)} />
      )}
      {dialog?.kind === 'reject' && dialog.p && (
        <ReasonDialog title="Reject payment" placeholder="e.g. Not on the bank statement"
          message={<>Reject <span className="mono">{dialog.p.number}</span> ({money(dialog.p.amount)} ETB)? It no longer counts as paid; {dialog.p.recorded_by_name} is told.</>}
          confirmLabel="Reject payment" onConfirm={(reason) => reject.mutateAsync({ id: dialog.p!.id, reason })} onClose={() => setDialog(null)} />
      )}
    </main>
  )
}
