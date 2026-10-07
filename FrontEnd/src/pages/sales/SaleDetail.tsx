import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import { useAction, useApi } from '../../api/hooks'
import type { Order, Payment } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { ConfirmDialog, ReasonDialog } from '../../components/Dialog'
import { Banner, Card, CondTag, DocLink, Empty, ErrorBanner, EthDate, KindBadge, Loading, Money, PageHeader, StatusChip } from '../../components/ui'
import { money } from '../../lib/format'
import { label } from '../../lib/labels'
import { EditDraftDialog, HandOverDialog, RequestStockDialog, ReturnDialog } from './SaleDialogs'

type Dialog = 'edit' | 'confirm' | 'handover' | 'request' | 'prepared' | 'cancel' | 'return' | 'void' | null

// P-42 Sale detail: lines with what is released, held, returned and paid; payments; delivery
// notes; and every action this status and this user allow.
export default function SaleDetail() {
  const { id } = useParams()
  const { user, can, is } = useAuth()
  const q = useApi<Order>(`/orders/${id}/`)
  const payments = useApi<{ payments: Payment[] }>(`/orders/${id}/payments/`)
  const [dialog, setDialog] = useState<Dialog>(null)
  const act = useAction(({ path, body }: { path: string; body?: unknown }) => api.post(`/orders/${id}/${path}/`, body ?? {}), { toastErrors: false, success: 'Done.' })

  if (q.isLoading) return <main className="page"><Loading /></main>
  if (q.error || !q.data) return <main className="page"><ErrorBanner error={q.error} /></main>
  const o = q.data
  const lines = o.lines ?? []
  const s = o.fulfillment_status
  const editable = s === 'draft' || s === 'pending'
  const billable = ['confirmed', 'prepared', 'partially_released', 'released'].includes(s)
  const salesStaff = is('salesperson', 'accountant', 'admin')
  const own = is('accountant', 'admin') || o.salesperson === user?.id
  const anyHandedOver = lines.some((l) => l.qty_released > 0)
  const canHandOver = billable && salesStaff && own && s !== 'released' && lines.some((l) => l.source_location_code === o.branch_code ? l.qty - l.qty_released - l.qty_returned > 0 : l.qty_awaiting > 0)
  const canRequest = billable && salesStaff && own && lines.some((l) => l.source_location_code !== o.branch_code && l.qty - l.qty_released - l.qty_awaiting - l.qty_returned > 0)
    && !(o.stock_requests ?? []).some((r) => ['pending', 'acknowledged', 'partially_released'].includes(r.status))
  const canReturn = billable && is('accountant', 'admin') && anyHandedOver
  const canVoid = billable && can('correct_transactions') && !(o.returns ?? []).length
  const canCancel = (editable || billable) && salesStaff && own && !anyHandedOver
  const canPrepare = is('storekeeper', 'admin') && o.channel === 'phone' && s === 'confirmed'
  const remaining = Number(o.remaining)

  return (
    <main className="page">
      <Link to="/sales" style={{ fontSize: 14 }}>← Sales</Link>
      <PageHeader
        title={<span className="row" style={{ gap: 12 }}><span className="mono">{o.number}</span><StatusChip kind="fulfilment" value={s} />{billable && <StatusChip kind="orderPayment" value={o.payment_status} />}</span>}
        sub={<>{label(o.channel)} · {label(o.receipt_type)} · {o.branch_code} · {o.salesperson_name} · <EthDate ec={o.created_at_ec} /></>}
        actions={<>
          {editable && own && salesStaff && <button type="button" className="btn btn-sec" onClick={() => setDialog('edit')}>Edit</button>}
          {canCancel && <button type="button" className="btn btn-dan" onClick={() => setDialog('cancel')}>Cancel…</button>}
          {canVoid && <button type="button" className="btn btn-dan" onClick={() => setDialog('void')}>Void…</button>}
          {canReturn && <button type="button" className="btn btn-sec" onClick={() => setDialog('return')}>Return goods</button>}
          {canRequest && <button type="button" className="btn btn-sec" onClick={() => setDialog('request')}>Request remaining stock</button>}
          {canPrepare && <button type="button" className="btn btn-sec" onClick={() => setDialog('prepared')}>Mark prepared</button>}
          {canHandOver && <button type="button" className="btn btn-sec" onClick={() => setDialog('handover')}>Hand over at branch</button>}
          {billable && remaining > 0 && salesStaff && <Link className="btn btn-sec" to={`/payments/new?order=${o.id}`}>Record payment</Link>}
          {editable && own && salesStaff && <button type="button" className="btn btn-pri" onClick={() => setDialog('confirm')}>Confirm</button>}
          <Link className="btn btn-sec" to={`/transactions/${o.number}`}>History</Link>
        </>} />
      {o.replaces && <Banner kind="info"><span>Replaces the voided sale <DocLink number={o.replaces} />.</span></Banner>}
      {o.replaced_by && <Banner kind="warn"><span>Voided and replaced by <DocLink number={o.replaced_by} />.</span></Banner>}
      {s === 'voided' && !o.replaced_by && can('correct_transactions') && (
        <Banner kind="warn"><span>This sale was voided{o.close_reason && `: “${o.close_reason}”`}. <Link to={`/sales/new?replaces=${o.id}`}>Re-issue corrected sale</Link></span></Banner>
      )}
      {(s === 'cancelled' || (s === 'voided' && o.replaced_by)) && o.close_reason && <Banner kind="info">Reason: “{o.close_reason}”</Banner>}

      <div className="grid-tiles">
        <Link className="tile" to={`/customers/${o.customer}`}><span className="lbl">Customer</span><span style={{ fontSize: 18, fontWeight: 600 }}>{o.customer_name}</span><span className="sub">{label(o.customer_type)}</span></Link>
        <div className="tile"><span className="lbl">Total</span><span className="tile-value">{money(o.total)}</span><span className="sub">ETB</span></div>
        <div className="tile"><span className="lbl">Paid</span><span className="tile-value">{money(o.paid)}</span></div>
        <div className="tile tile-dark"><span className="lbl">Remaining</span><span className="tile-value">{money(o.remaining)}</span><span className="sub">{remaining > 0 && billable ? 'owed (credit)' : ' '}</span></div>
      </div>

      <Card title="Lines">
        <div style={{ overflowX: 'auto' }}>
          <table className="tbl">
            <thead><tr><th>Product</th><th>Condition</th><th className="r">Qty</th><th className="r">Unit price</th><th className="r">Discount</th><th className="r">Line total</th><th>Source</th><th className="r">Released</th><th className="r">Held here</th><th className="r">Returned</th><th className="r">Paid</th><th className="r">Remaining</th></tr></thead>
            <tbody>
              {lines.map((l) => (
                <tr key={l.id}>
                  <td><Link className="mono" to={`/products/${l.product}`} style={{ fontWeight: 600 }}>{l.product_code}</Link> <span className="sub">{l.product_name}</span></td>
                  <td><CondTag condition={l.condition} /></td>
                  <td className="r">{l.qty}</td>
                  <td className="r">{money(l.unit_price)}</td>
                  <td className="r">{Number(l.discount) ? money(l.discount) : '—'}</td>
                  <td className="r" style={{ fontWeight: 600 }}>{money(l.line_total)}</td>
                  <td>{l.source_location_code}</td>
                  <td className="r">{l.qty_released}</td>
                  <td className="r" style={l.qty_awaiting ? { color: 'var(--blue-fg)', fontWeight: 600 } : { color: 'var(--faint)' }}>{l.qty_awaiting}</td>
                  <td className="r" style={l.qty_returned ? undefined : { color: 'var(--faint)' }}>{l.qty_returned}</td>
                  <td className="r">{l.paid === null ? <Money value={null} hidden /> : money(l.paid)}</td>
                  <td className="r">{money(l.remaining)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {o.notes && <span className="sub">Notes: {o.notes}</span>}
      </Card>

      <div className="grid-cards">
        <Card title="Payments" actions={billable && remaining > 0 && salesStaff && <Link to={`/payments/new?order=${o.id}`} style={{ fontSize: 13 }}>Record payment</Link>}>
          {!payments.data?.payments.length ? <Empty title="No payments yet" /> : (
            <div style={{ overflowX: 'auto' }}>
              <table className="tbl">
                <thead><tr><th>Date</th><th>Payment</th><th className="r">Amount</th><th>Account</th><th>Status</th><th>Recorded by</th></tr></thead>
                <tbody>
                  {payments.data.payments.map((p) => (
                    <tr key={p.id}>
                      <td><EthDate value={p.paid_at} time={false} /></td>
                      <td><DocLink number={p.number} to={`/payments/${p.id}`} /></td>
                      <td className="r"><Money value={p.amount} hidden={p.hidden} strong /></td>
                      <td><span className="row" style={{ gap: 6 }}><KindBadge kind={p.account_kind} short />{p.account_name ?? ''}</span></td>
                      <td><StatusChip kind="payment" value={p.status} /></td>
                      <td>{p.recorded_by_name}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
        <div className="stack" style={{ gap: 20 }}>
          <Card title="Delivery notes">
            {!o.delivery_notes?.length ? <Empty title="Nothing handed over yet" /> : o.delivery_notes.map((dn) => (
              <div className="card-row" key={dn.id}>
                <div className="grow stack" style={{ gap: 2 }}>
                  <span><span className="mono">{dn.number}</span> · {dn.location_code}</span>
                  <span className="sub">{dn.issued_at_ec} · {dn.lines.map((l) => `${l.qty} × ${l.product_code}`).join(', ')}</span>
                </div>
                <Link className="btn btn-sec btn-sm" to={`/delivery-notes/${dn.id}`} target="_blank">Print</Link>
              </div>
            ))}
          </Card>
          <Card title="Stock requests">
            {!o.stock_requests?.length ? <Empty title="None — taken from the branch" /> : o.stock_requests.map((r) => (
              <div className="card-row" key={r.id}>
                <DocLink number={r.number} to={`/stock-requests/${r.id}`} /><span className="grow muted">from {String(r.source_location_code ?? '')}</span><StatusChip kind="request" value={r.status} />
              </div>
            ))}
          </Card>
          {(o.returns ?? []).length > 0 && (
            <Card title="Returns">
              {o.returns!.map((r) => (
                <div className="card-row" key={r.number}>
                  <span className="mono">{r.number}</span><span className="grow muted">{r.reason}</span><Money value={r.amount ?? null} strong />
                </div>
              ))}
            </Card>
          )}
        </div>
      </div>

      {dialog === 'edit' && <EditDraftDialog order={o} onClose={() => setDialog(null)} />}
      {dialog === 'handover' && <HandOverDialog order={o} onClose={() => setDialog(null)} />}
      {dialog === 'request' && <RequestStockDialog order={o} onClose={() => setDialog(null)} />}
      {dialog === 'return' && <ReturnDialog order={o} onClose={() => setDialog(null)} />}
      {dialog === 'confirm' && (
        <ConfirmDialog title="Confirm sale" message={<>Confirm <span className="mono">{o.number}</span> for {o.customer_name}, total <strong>{money(o.total)} ETB</strong>? Goods from {o.branch_code} are handed over now; warehouse lines become a stock request.{remaining > 0 && <> {money(o.remaining)} stays owed (credit).</>}</>}
          confirmLabel="Confirm" onConfirm={() => act.mutateAsync({ path: 'confirm' })} onClose={() => setDialog(null)} />
      )}
      {dialog === 'prepared' && (
        <ConfirmDialog title="Mark prepared" message={<>Mark <span className="mono">{o.number}</span> prepared? {o.customer_name} is told the goods are ready.</>}
          confirmLabel="Mark prepared" onConfirm={() => act.mutateAsync({ path: 'status', body: { status: 'prepared' } })} onClose={() => setDialog(null)} />
      )}
      {dialog === 'cancel' && (
        <ReasonDialog title="Cancel sale" message={<>Cancel <span className="mono">{o.number}</span>? Reserved stock is freed and open stock requests are closed. Payments stay as the customer's credit.</>}
          confirmLabel="Cancel sale" onConfirm={(reason) => act.mutateAsync({ path: 'cancel', body: { reason } })} onClose={() => setDialog(null)} />
      )}
      {dialog === 'void' && (
        <ReasonDialog title="Void sale" message={<>Void <span className="mono">{o.number}</span> — for a sale entered wrongly. Stock goes back, the sale leaves the customer's balance, its payments become the customer's credit. Then you can re-issue a corrected sale.</>}
          confirmLabel="Void sale" onConfirm={(reason) => act.mutateAsync({ path: 'void', body: { reason } })} onClose={() => setDialog(null)} />
      )}
    </main>
  )
}
