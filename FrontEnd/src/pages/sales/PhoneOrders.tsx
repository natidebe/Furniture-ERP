import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import { useAction, useApi } from '../../api/hooks'
import type { Order, Paginated } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { ConfirmDialog } from '../../components/Dialog'
import { DocLink, Empty, Loading, PageHeader, StatusChip } from '../../components/ui'
import { money } from '../../lib/format'

const COLUMNS: [string, string, string][] = [
  ['pending', 'Pending', 'Waiting for confirmation'],
  ['confirmed', 'Confirmed', 'Storekeeper prepares'],
  ['prepared', 'Prepared', 'Ready for pickup'],
  ['partially_released', 'Partially released', 'Some goods collected'],
  ['released', 'Released', 'Collected'],
]

// P-44 Phone orders board: Pending → Confirmed → Prepared → Released. No company delivery (D8):
// the customer collects (release on the request as Customer pickup).
export default function PhoneOrders() {
  const { is } = useAuth()
  return (
    <main className="page">
      <PageHeader title="Phone orders" sub="Out-of-city and phone orders, by status · customers collect (no company delivery)"
        actions={is('salesperson', 'accountant', 'admin') && <Link className="btn btn-pri" to="/sales/new">New sale</Link>} />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16, alignItems: 'start' }}>
        {COLUMNS.map(([status, title, hint]) => <Column key={status} status={status} title={title} hint={hint} />)}
      </div>
    </main>
  )
}

function Column({ status, title, hint }: { status: string; title: string; hint: string }) {
  const { is } = useAuth()
  const q = useApi<Paginated<Order>>('/orders/', { channel: 'phone', status, ordering: '-created_at', page_size: 50 })
  const [prepare, setPrepare] = useState<Order | null>(null)
  const mark = useAction((id: number) => api.post(`/orders/${id}/status/`, { status: 'prepared' }), { success: 'Marked prepared.', toastErrors: false })
  return (
    <section className="stack" style={{ gap: 10 }}>
      <div className="spread"><h2>{title} <span className="sub">{q.data?.count ?? ''}</span></h2></div>
      <span className="sub" style={{ marginTop: -8 }}>{hint}</span>
      {q.isLoading ? <Loading /> : q.data?.results.length === 0 ? <div className="card"><Empty title="None" /></div> : q.data?.results.map((o) => (
        <article key={o.id} className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div className="spread"><DocLink number={o.number} to={`/sales/${o.id}`} strong /><StatusChip kind="orderPayment" value={o.payment_status} /></div>
          <span style={{ fontWeight: 600 }}>{o.customer_name}</span>
          <span className="sub">{o.branch_code} · {o.salesperson_name} · {o.created_at_ec.split(' (')[0]}</span>
          <div className="spread"><span className="sub">Total</span><span className="num" style={{ fontWeight: 600 }}>{money(o.total)}</span></div>
          {Number(o.remaining) > 0 && <div className="spread"><span className="sub">Remaining</span><span className="num">{money(o.remaining)}</span></div>}
          {status === 'confirmed' && is('storekeeper', 'admin') && <button type="button" className="btn btn-pri btn-sm" onClick={() => setPrepare(o)}>Mark prepared</button>}
          {status === 'pending' && is('salesperson', 'accountant', 'admin') && <Link className="btn btn-sec btn-sm" to={`/sales/${o.id}`}>Open to confirm</Link>}
        </article>
      ))}
      {prepare && (
        <ConfirmDialog title="Mark prepared" message={<>Mark <span className="mono">{prepare.number}</span> for {prepare.customer_name} prepared? The salesperson is told the goods are ready for pickup.</>}
          confirmLabel="Mark prepared" onConfirm={() => mark.mutateAsync(prepare.id)} onClose={() => setPrepare(null)} />
      )}
    </section>
  )
}
