import { Link } from 'react-router-dom'
import { useApi, useRealLocations } from '../../api/hooks'
import type { Order, Paginated } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { EthDatePicker } from '../../components/EthDatePicker'
import { SearchInput } from '../../components/inputs'
import { DocLink, EthDate, Field, PageHeader, Pager, QueryState, StatusChip } from '../../components/ui'
import { money } from '../../lib/format'
import { label } from '../../lib/labels'
import { useFilters } from '../../lib/useFilters'

const FULFILMENT = ['draft', 'pending', 'confirmed', 'prepared', 'partially_released', 'released', 'cancelled', 'voided']

// P-41 Sales. Salespeople see only their own (D9); storekeepers the sales their warehouse supplies.
export default function Sales() {
  const { is } = useAuth()
  const { values: f, set, setMany, page, setPage } = useFilters(['search', 'status', 'payment_status', 'owing', 'branch', 'channel', 'receipt_type', 'from', 'to'] as const)
  const { data: locations } = useRealLocations()
  const q = useApi<Paginated<Order>>('/orders/', { ...f, ordering: '-created_at', page })
  const payValue = f.owing === 'true' ? 'owing' : f.payment_status

  return (
    <main className="page">
      <PageHeader title={is('salesperson') ? 'My sales' : 'Sales'} sub={q.data ? `${q.data.count} sales` : ' '}
        actions={is('salesperson', 'accountant', 'admin') && <Link className="btn btn-pri" to="/sales/new">New sale</Link>} />
      <div className="filters">
        <Field label="Search" className="fld-search">{(id) => <SearchInput id={id} value={f.search} onChange={(v) => set('search', v)} placeholder="SO number, customer name or phone" />}</Field>
        <Field label="Status">{(id) => (
          <select id={id} className="inp" value={f.status} onChange={(e) => set('status', e.target.value)}>
            <option value="">All</option>{FULFILMENT.map((s) => <option key={s} value={s}>{label(s)}</option>)}
          </select>
        )}</Field>
        <Field label="Payment">{(id) => (
          <select id={id} className="inp" value={payValue} onChange={(e) => setMany(e.target.value === 'owing' ? { owing: 'true', payment_status: '' } : { owing: '', payment_status: e.target.value })}>
            <option value="">All</option><option value="owing">Waiting for payment</option><option value="unpaid">Unpaid</option><option value="partial">Partial</option><option value="paid">Paid</option>
          </select>
        )}</Field>
        {!is('salesperson') && (
          <Field label="Branch">{(id) => (
            <select id={id} className="inp" value={f.branch} onChange={(e) => set('branch', e.target.value)}>
              <option value="">All branches</option>{locations?.filter((l) => l.can_sell).map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          )}</Field>
        )}
        <Field label="Channel">{(id) => (
          <select id={id} className="inp" value={f.channel} onChange={(e) => set('channel', e.target.value)}>
            <option value="">Any</option><option value="walk_in">Walk-in</option><option value="phone">Phone order</option>
          </select>
        )}</Field>
        <Field label="Receipt">{(id) => (
          <select id={id} className="inp" value={f.receipt_type} onChange={(e) => set('receipt_type', e.target.value)}>
            <option value="">Any</option><option value="official">Official receipt</option><option value="none">Without receipt</option>
          </select>
        )}</Field>
        <Field label="From" style={{ flex: '0 1 240px' }}>{(id) => <EthDatePicker id={id} value={f.from} onChange={(v) => set('from', v)} />}</Field>
        <Field label="To" style={{ flex: '0 1 240px' }}>{(id) => <EthDatePicker id={id} value={f.to} onChange={(v) => set('to', v)} />}</Field>
      </div>
      <div className="tw">
        <QueryState query={q} empty={q.data?.results.length === 0} emptyHint="No sales match">
          <table className="tbl">
            <thead><tr><th>Sale</th><th>Date</th><th>Customer</th><th>Branch</th><th>Salesperson</th><th>Channel</th><th className="r">Total</th><th className="r">Paid</th><th className="r">Remaining</th><th>Status</th><th>Payment</th><th>Receipt</th></tr></thead>
            <tbody>
              {q.data?.results.map((o) => (
                <tr key={o.id}>
                  <td><DocLink number={o.number} to={`/sales/${o.id}`} strong /></td>
                  <td><EthDate ec={o.created_at_ec} /></td>
                  <td><Link to={`/customers/${o.customer}`} style={{ color: 'var(--ink)' }}>{o.customer_name}</Link></td>
                  <td>{o.branch_code}</td>
                  <td>{o.salesperson_name}</td>
                  <td>{label(o.channel)}</td>
                  <td className="r">{money(o.total)}</td>
                  <td className="r">{money(o.paid)}</td>
                  <td className="r" style={{ fontWeight: 600 }}>{money(o.remaining)}</td>
                  <td><StatusChip kind="fulfilment" value={o.fulfillment_status} /></td>
                  <td><StatusChip kind="orderPayment" value={o.payment_status} /></td>
                  <td>{o.receipt_type === 'official' ? 'Official' : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </QueryState>
      </div>
      <Pager page={page} count={q.data?.count ?? 0} onPage={setPage} />
    </main>
  )
}
