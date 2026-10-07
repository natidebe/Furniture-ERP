import { Link } from 'react-router-dom'
import { useApi, usePaymentAccounts } from '../../api/hooks'
import type { Paginated, Payment } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { EthDatePicker } from '../../components/EthDatePicker'
import { SearchInput } from '../../components/inputs'
import { DocLink, EthDate, Field, KindBadge, Money, PageHeader, Pager, QueryState, StatusChip } from '../../components/ui'
import { money } from '../../lib/format'
import { label } from '../../lib/labels'
import { useFilters } from '../../lib/useFilters'

// P-51 Payments, with Organization · Personal · Combined totals for the current filters
// (from the payments report). Salespeople see what they recorded or what pays their sales.
export default function Payments() {
  const { can, is } = useAuth()
  const { values: f, set, page, setPage } = useFilters(['search', 'number', 'status', 'account', 'account_kind', 'from', 'to'] as const)
  const { data: accounts } = usePaymentAccounts()
  const q = useApi<Paginated<Payment>>('/payments/', { ...f, ordering: '-paid_at', page })
  const totalsParams = { from: f.from || '2000-01-01', to: f.to || '2100-12-31', account: f.account, account_kind: f.account_kind }
  const totals = useApi<{ totals?: { organization: string; personal: string | null; combined: string | null } } & Record<string, unknown>>(is('accountant', 'admin') ? '/reports/payments/' : null, totalsParams)
  const t = totals.data?.totals

  return (
    <main className="page">
      <PageHeader title="Payments" sub={q.data ? `${q.data.count} payments` : ' '}
        actions={<>
          {can('verify_payments') && <Link className="btn btn-sec" to="/payments/verify">Payments to verify</Link>}
          <Link className="btn btn-pri" to="/payments/new">Record payment</Link>
        </>} />
      {t && (
        <div className="grid-tiles">
          <div className="tile"><KindBadge kind="organization" /><span className="tile-value">{money(t.organization)}</span><span className="sub">for the dates and account chosen</span></div>
          <div className="tile"><KindBadge kind="personal" /><span className="tile-value">{t.personal === null ? '—' : money(t.personal)}</span><span className="sub">{t.personal === null ? 'hidden' : ' '}</span></div>
          <div className="tile tile-dark"><span className="lbl">Combined</span><span className="tile-value">{t.combined === null ? '—' : money(t.combined)}</span></div>
        </div>
      )}
      <div className="filters">
        <Field label="Search" className="fld-search">{(id) => <SearchInput id={id} value={f.search} onChange={(v) => set('search', v)} placeholder="PAY number, receipt or customer" />}</Field>
        <Field label="Status">{(id) => (
          <select id={id} className="inp" value={f.status} onChange={(e) => set('status', e.target.value)}>
            <option value="">All</option><option value="unverified">Unverified</option><option value="verified">Verified</option><option value="rejected">Rejected</option><option value="reversed">Reversed</option>
          </select>
        )}</Field>
        <Field label="Kind">{(id) => (
          <select id={id} className="inp" value={f.account_kind} onChange={(e) => set('account_kind', e.target.value)}>
            <option value="">Both</option><option value="organization">Organization</option><option value="personal">Personal</option>
          </select>
        )}</Field>
        <Field label="Account">{(id) => (
          <select id={id} className="inp" value={f.account} onChange={(e) => set('account', e.target.value)}>
            <option value="">All accounts</option>{accounts?.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        )}</Field>
        <Field label="From" style={{ flex: '0 1 240px' }}>{(id) => <EthDatePicker id={id} value={f.from} onChange={(v) => set('from', v)} />}</Field>
        <Field label="To" style={{ flex: '0 1 240px' }}>{(id) => <EthDatePicker id={id} value={f.to} onChange={(v) => set('to', v)} />}</Field>
      </div>
      <div className="tw">
        <QueryState query={q} empty={q.data?.results.length === 0} emptyHint="No payments match">
          <table className="tbl">
            <thead><tr><th>Payment</th><th>Date</th><th>Customer</th><th className="r">Amount</th><th>Account</th><th>Method</th><th>Receipt</th><th>Status</th><th>Recorded by</th><th>For</th></tr></thead>
            <tbody>
              {q.data?.results.map((p) => (
                <tr key={p.id}>
                  <td><DocLink number={p.number} to={`/payments/${p.id}`} strong /></td>
                  <td><EthDate value={p.paid_at} /></td>
                  <td><Link to={`/customers/${p.customer}`} style={{ color: 'var(--ink)' }}>{p.customer_name}</Link></td>
                  <td className="r"><Money value={p.amount} hidden={p.hidden} strong /></td>
                  <td><span className="row" style={{ gap: 6, flexWrap: 'nowrap' }}><KindBadge kind={p.account_kind} short />{p.account_name ?? '—'}</span></td>
                  <td>{label(p.method)}</td>
                  <td className="mono" style={{ fontSize: 13 }}>{p.receipt_number ?? '—'}</td>
                  <td><StatusChip kind="payment" value={p.status} /></td>
                  <td>{p.recorded_by_name}</td>
                  <td className="wrap">{p.allocations.filter((a) => a.is_active).map((a) => a.order_number + (a.product_code ? ` (${a.product_code})` : '')).join(', ') || <span className="muted">Advance</span>}</td>
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
