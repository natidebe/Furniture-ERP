import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useApi } from '../../api/hooks'
import type { Customer, CustomerBalance, Order, Paginated, Payment, Statement, StockRequest } from '../../api/types'
import { EthDatePicker } from '../../components/EthDatePicker'
import { Card, DocLink, Empty, ErrorBanner, EthDate, Field, KindBadge, Loading, Money, PageHeader, StatusChip, Tabs } from '../../components/ui'
import { money } from '../../lib/format'
import { label } from '../../lib/labels'

// P-61 Customer detail & statement — "ABC Furniture: Total purchases 500,000 · Payments 350,000
// · Outstanding 150,000".
export default function CustomerDetail() {
  const { id } = useParams()
  const customer = useApi<Customer>(`/customers/${id}/`)
  const balance = useApi<CustomerBalance>(`/customers/${id}/balance/`)
  const [range, setRange] = useState({ from: '', to: '' })
  const statement = useApi<Statement>(`/customers/${id}/statement/`, range)
  const [tab, setTab] = useState<'statement' | 'sales' | 'payments' | 'requests'>('statement')
  const sales = useApi<Paginated<Order>>(tab === 'sales' ? '/orders/' : null, { customer: id })
  const payments = useApi<Paginated<Payment>>(tab === 'payments' ? '/payments/' : null, { customer: id })
  const requests = useApi<Paginated<StockRequest>>(tab === 'requests' ? '/stock-requests/' : null, { customer: id })

  if (customer.isLoading) return <main className="page"><Loading /></main>
  if (customer.error || !customer.data) return <main className="page"><ErrorBanner error={customer.error} /></main>
  const c = customer.data
  const b = balance.data

  return (
    <main className="page">
      <Link to="/customers" className="no-print" style={{ fontSize: 14 }}>← Customers</Link>
      <PageHeader
        title={<span className="row" style={{ gap: 12 }}>{c.name}{c.over_limit && <span className="chip c-amber">Over limit</span>}{!c.is_active && <span className="chip c-grey">Inactive</span>}</span>}
        sub={[label(c.type), c.shop_name, c.city, c.phone].filter(Boolean).join(' · ')}
        actions={<span className="row no-print">
          <Link className="btn btn-sec" to={`/customers/${c.id}/edit`}>Edit</Link>
          <Link className="btn btn-sec" to={`/payments/new?customer=${c.id}`}>Record payment</Link>
          <Link className="btn btn-pri" to="/sales/new">New sale</Link>
        </span>} />
      <div className="grid-tiles">
        <div className="tile"><span className="lbl">Total purchases</span><span className="tile-value">{money(b?.total_purchases)}</span></div>
        <div className="tile"><span className="lbl">Total paid</span><span className="tile-value">{money(b?.total_paid)}</span></div>
        <div className="tile tile-dark"><span className="lbl">Outstanding</span><span className="tile-value">{money(b?.outstanding)}</span><span className="sub">ETB owed now</span></div>
        {b && Number(b.prepaid) > 0 && <div className="tile"><span className="lbl">Prepaid</span><span className="tile-value">{money(b.prepaid)}</span><span className="sub">paid beyond purchases</span></div>}
        {b && Number(b.unallocated) > 0 && <div className="tile"><span className="lbl">Advance (unallocated)</span><span className="tile-value">{money(b.unallocated)}</span><span className="sub">not yet tied to a sale</span></div>}
        <div className="tile"><span className="lbl">Credit</span><span className="tile-value" style={{ fontSize: 20 }}>{c.credit_allowed ? (c.credit_limit ? money(c.credit_limit) : 'No limit') : 'Not allowed'}</span><span className="sub">{c.credit_allowed ? 'limit' : 'pays at once'}</span></div>
      </div>
      <div className="no-print"><Tabs value={tab} onChange={setTab} options={[['statement', 'Statement'], ['sales', 'Sales'], ['payments', 'Payments'], ['requests', 'Stock requests']]} /></div>

      {tab === 'statement' && (
        <Card title="Statement" actions={<button type="button" className="btn btn-sec btn-sm no-print" onClick={() => window.print()}>Print</button>}>
          <div className="filters no-print">
            <Field label="From" style={{ flex: '0 1 260px' }}>{(fid) => <EthDatePicker id={fid} value={range.from} onChange={(v) => setRange({ ...range, from: v })} />}</Field>
            <Field label="To" style={{ flex: '0 1 260px' }}>{(fid) => <EthDatePicker id={fid} value={range.to} onChange={(v) => setRange({ ...range, to: v })} />}</Field>
          </div>
          {statement.data && (
            <div style={{ overflowX: 'auto' }}>
              <table className="tbl">
                <thead><tr><th>Date</th><th>Document</th><th>Description</th><th className="r">Debit</th><th className="r">Credit</th><th className="r">Balance</th></tr></thead>
                <tbody>
                  <tr><td colSpan={5} className="muted">Opening balance</td><td className="r" style={{ fontWeight: 600 }}>{money(statement.data.opening_balance)}</td></tr>
                  {statement.data.rows.map((r) => (
                    <tr key={`${r.kind}-${r.number}`}>
                      <td>{r.date_ec}</td>
                      <td><DocLink number={r.number} /></td>
                      <td className="wrap">{r.description} {r.account_kind && <KindBadge kind={r.account_kind} short />}</td>
                      <td className="r">{r.debit ? money(r.debit) : ''}</td>
                      <td className="r">{r.hidden ? <Money value={null} hidden /> : r.credit ? money(r.credit) : ''}</td>
                      <td className="r" style={{ fontWeight: 600 }}>{money(r.balance)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot><tr><td colSpan={5}>Closing balance</td><td className="r">{money(statement.data.closing_balance)}</td></tr></tfoot>
              </table>
            </div>
          )}
          {statement.data?.rows.length === 0 && <Empty title="Nothing in this period" />}
        </Card>
      )}
      {tab === 'sales' && (
        <div className="tw">
          {sales.data?.results.length === 0 ? <Empty title="No sales yet" /> : (
            <table className="tbl">
              <thead><tr><th>Sale</th><th>Date</th><th>Branch</th><th className="r">Total</th><th className="r">Remaining</th><th>Status</th><th>Payment</th></tr></thead>
              <tbody>{sales.data?.results.map((o) => (
                <tr key={o.id}>
                  <td><DocLink number={o.number} to={`/sales/${o.id}`} strong /></td><td><EthDate ec={o.created_at_ec} /></td><td>{o.branch_code}</td>
                  <td className="r">{money(o.total)}</td><td className="r">{money(o.remaining)}</td>
                  <td><StatusChip kind="fulfilment" value={o.fulfillment_status} /></td><td><StatusChip kind="orderPayment" value={o.payment_status} /></td>
                </tr>
              ))}</tbody>
            </table>
          )}
        </div>
      )}
      {tab === 'payments' && (
        <div className="tw">
          {payments.data?.results.length === 0 ? <Empty title="No payments yet" /> : (
            <table className="tbl">
              <thead><tr><th>Payment</th><th>Date</th><th className="r">Amount</th><th>Account</th><th>Receipt</th><th>Status</th></tr></thead>
              <tbody>{payments.data?.results.map((p) => (
                <tr key={p.id}>
                  <td><DocLink number={p.number} to={`/payments/${p.id}`} strong /></td><td><EthDate value={p.paid_at} /></td>
                  <td className="r"><Money value={p.amount} hidden={p.hidden} /></td>
                  <td><span className="row" style={{ gap: 6 }}><KindBadge kind={p.account_kind} short />{p.account_name ?? '—'}</span></td>
                  <td className="mono" style={{ fontSize: 13 }}>{p.receipt_number ?? '—'}</td>
                  <td><StatusChip kind="payment" value={p.status} /></td>
                </tr>
              ))}</tbody>
            </table>
          )}
        </div>
      )}
      {tab === 'requests' && (
        <div className="tw">
          {requests.data?.results.length === 0 ? <Empty title="No stock requests" /> : (
            <table className="tbl">
              <thead><tr><th>Request</th><th>Date</th><th>Lines</th><th>Status</th></tr></thead>
              <tbody>{requests.data?.results.map((r) => (
                <tr key={r.id}><td><DocLink number={r.number} to={`/stock-requests/${r.id}`} strong /></td><td><EthDate value={r.created_at} /></td>
                  <td>{r.lines.map((l) => `${l.qty_requested} × ${l.product_code}`).join(', ')}</td><td><StatusChip kind="request" value={r.status} /></td></tr>
              ))}</tbody>
            </table>
          )}
        </div>
      )}
    </main>
  )
}
