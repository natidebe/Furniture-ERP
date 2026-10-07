import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import { useAction, useApi } from '../../api/hooks'
import type { StockRequest } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { ConfirmDialog, ReasonDialog } from '../../components/Dialog'
import { Banner, Card, DocLink, Empty, ErrorBanner, EthDate, Loading, PageHeader, StatusChip } from '../../components/ui'
import { label } from '../../lib/labels'

type Act = 'acknowledge' | 'reject' | 'cancel' | 'close'

// P-32 Stock request detail. Only the buttons valid for this status and person are shown:
//   Pending:            storekeeper Acknowledge · Reject; requester Cancel
//   Acknowledged:       storekeeper Release · Reject; requester Cancel
//   Partially released: storekeeper Release · Close; requester Close
//   Released:           Close
export default function StockRequestDetail() {
  const { id } = useParams()
  const { user, is } = useAuth()
  const q = useApi<StockRequest>(`/stock-requests/${id}/`)
  const [act, setAct] = useState<Act | null>(null)
  const run = useAction(({ action, reason }: { action: Act; reason?: string }) =>
    api.post(`/stock-requests/${id}/${action}/`, reason ? { reason } : {}), { toastErrors: false, success: 'Done.' })

  if (q.isLoading) return <main className="page"><Loading /></main>
  if (q.error || !q.data) return <main className="page"><ErrorBanner error={q.error} /></main>
  const r = q.data
  const admin = is('admin')
  const source = admin || (is('storekeeper') && user?.home_location === r.source_location)
  const requester = admin || r.salesperson === user?.id
  const s = r.status
  const can = {
    acknowledge: source && s === 'pending',
    release: source && (s === 'acknowledged' || s === 'partially_released'),
    reject: source && (s === 'pending' || s === 'acknowledged'),
    cancel: requester && (s === 'pending' || s === 'acknowledged'),
    close: (source || requester) && (s === 'partially_released' || s === 'released'),
  }
  const lines = r.lines.map((l) => `${l.qty_requested} × ${l.product_code}`).join(', ')
  const ext = r as StockRequest & { acknowledged_by_name?: string; closed_by_name?: string }

  return (
    <main className="page">
      <Link to="/stock-requests" style={{ fontSize: 14 }}>← Stock requests</Link>
      <PageHeader
        title={<span className="row" style={{ gap: 12 }}><span className="mono">{r.number}</span><StatusChip kind="request" value={s} /></span>}
        sub={<>{r.requesting_location_code} → {r.source_location_code}{r.transaction_number !== r.number && <> · for <DocLink number={r.transaction_number} /></>}</>}
        actions={<>
          {can.cancel && <button type="button" className="btn btn-dan" onClick={() => setAct('cancel')}>Cancel…</button>}
          {can.reject && <button type="button" className="btn btn-dan" onClick={() => setAct('reject')}>Reject…</button>}
          {can.close && <button type="button" className="btn btn-sec" onClick={() => setAct('close')}>Close…</button>}
          {can.acknowledge && <button type="button" className="btn btn-pri" onClick={() => setAct('acknowledge')}>Acknowledge</button>}
          {can.release && <Link className="btn btn-pri" to={`/stock-requests/${r.id}/release`}>Release stock</Link>}
          <Link className="btn btn-sec" to={`/transactions/${r.transaction_number}`}>History</Link>
        </>} />
      {s === 'pending' && is('storekeeper') && can.acknowledge && <Banner kind="info">Acknowledge first, then release. The branch sees that you are on it.</Banner>}
      <div className="grid-cards" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(380px, 100%), 1fr))' }}>
        <Card title="Request">
          <dl className="dl">
            <dt>Branch</dt><dd>{r.requesting_location_code}</dd>
            <dt>From</dt><dd>{r.source_location_code}</dd>
            <dt>Customer</dt><dd>{r.customer ? <Link to={`/customers/${r.customer}`}>{r.customer_name}</Link> : '—'}</dd>
            <dt>Reference</dt><dd>{r.reference || '—'}</dd>
            <dt>Salesperson</dt><dd>{r.salesperson_name}</dd>
            <dt>Created</dt><dd><EthDate value={r.created_at} /></dd>
            <dt>Acknowledged</dt><dd>{r.acknowledged_at ? <><EthDate value={r.acknowledged_at} />{ext.acknowledged_by_name && ` by ${ext.acknowledged_by_name}`}</> : '—'}</dd>
            {r.closed_at && <><dt>{label(s)}</dt><dd><EthDate value={r.closed_at} />{ext.closed_by_name && ` by ${ext.closed_by_name}`}{r.close_reason && <div className="sub">“{r.close_reason}”</div>}</dd></>}
            {r.notes && <><dt>Notes</dt><dd>{r.notes}</dd></>}
          </dl>
        </Card>
        <Card title="Lines">
          <div style={{ overflowX: 'auto' }}>
            <table className="tbl">
              <thead><tr><th>Product</th><th className="r">Requested</th><th className="r">Released</th><th className="r">Remaining</th></tr></thead>
              <tbody>
                {r.lines.map((l) => (
                  <tr key={l.id}>
                    <td><Link className="mono" to={`/products/${l.product}`} style={{ fontWeight: 600 }}>{l.product_code}</Link> {l.product_name}</td>
                    <td className="r">{l.qty_requested}</td>
                    <td className="r">{l.qty_released}</td>
                    <td className="r" style={{ fontWeight: 600, color: l.qty_remaining ? 'var(--blue-fg)' : 'var(--faint)' }}>{l.qty_remaining}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
      <Card title="Releases">
        {r.releases.length === 0 ? <Empty title="Nothing released yet" /> : (
          <div style={{ overflowX: 'auto' }}>
            <table className="tbl">
              <thead><tr><th>Release</th><th>Date</th><th>Destination</th><th>Lines</th><th>By</th><th>Transfer</th></tr></thead>
              <tbody>
                {r.releases.map((rel) => {
                  const x = rel as typeof rel & { transfer_id?: number | null; transfer_status?: string | null }
                  return (
                    <tr key={rel.id}>
                      <td className="mono" style={{ fontSize: 13 }}>{rel.number}</td>
                      <td><EthDate value={rel.released_at} /></td>
                      <td>{label(rel.destination_type)}</td>
                      <td>{rel.lines.map((l) => `${l.qty} × ${l.product_code}`).join(', ')}</td>
                      <td>{rel.released_by_name}</td>
                      <td>{rel.transfer_number
                        ? <span className="row" style={{ gap: 6 }}><DocLink number={rel.transfer_number} to={x.transfer_id ? `/transfers/${x.transfer_id}` : undefined} />{x.transfer_status && <StatusChip kind="transfer" value={x.transfer_status} />}</span>
                        : <span className="muted">Customer collected</span>}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      {act === 'acknowledge' && <ConfirmDialog title="Acknowledge request" message={<>Acknowledge <span className="mono">{r.number}</span> ({lines})? {r.salesperson_name} is told you are on it.</>}
        confirmLabel="Acknowledge" onConfirm={() => run.mutateAsync({ action: 'acknowledge' })} onClose={() => setAct(null)} />}
      {act === 'reject' && <ReasonDialog title="Reject request" message={<>Reject <span className="mono">{r.number}</span>? The reserved stock is freed and {r.salesperson_name} is told.</>}
        confirmLabel="Reject request" onConfirm={(reason) => run.mutateAsync({ action: 'reject', reason })} onClose={() => setAct(null)} />}
      {act === 'cancel' && <ReasonDialog title="Cancel request" message={<>Cancel <span className="mono">{r.number}</span>? The reserved stock at {r.source_location_code} is freed.</>}
        confirmLabel="Cancel request" onConfirm={(reason) => run.mutateAsync({ action: 'cancel', reason })} onClose={() => setAct(null)} />}
      {act === 'close' && <ReasonDialog title="Close request" message={<>Close <span className="mono">{r.number}</span>? Nothing more will be released; any remaining reservation is freed.</>}
        confirmLabel="Close request" onConfirm={(reason) => run.mutateAsync({ action: 'close', reason })} onClose={() => setAct(null)} />}
    </main>
  )
}
