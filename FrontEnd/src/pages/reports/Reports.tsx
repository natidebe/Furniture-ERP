import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { download, errorMessage } from '../../api/client'
import { useApi, useCategories, usePaymentAccounts, useRealLocations } from '../../api/hooks'
import type { Role } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { PeriodPicker, periodParams } from '../../components/PeriodPicker'
import type { PeriodValue } from '../../components/PeriodPicker'
import { Card, CondTag, DocLink, Empty, ErrorBanner, Field, KindBadge, Loading, PageHeader, StatusChip } from '../../components/ui'
import { useToast } from '../../components/Toast'
import { money, pct } from '../../lib/format'
import { MOVEMENT_TYPES, label } from '../../lib/labels'

type Name = 'sales' | 'payments' | 'credit' | 'stock' | 'movements' | 'open-requests' | 'unverified-payments'
const TITLES: Record<Name, string> = {
  sales: 'Sales', payments: 'Payments', credit: 'Credit', stock: 'Stock', movements: 'Movements',
  'open-requests': 'Open requests', 'unverified-payments': 'Unverified payments',
}
const ALL: Name[] = ['sales', 'payments', 'credit', 'stock', 'movements', 'open-requests', 'unverified-payments']
const BY_ROLE: Record<Role, Name[]> = {
  salesperson: ['sales'], storekeeper: ['stock', 'movements', 'open-requests'], accountant: ALL, admin: ALL,
}
const DATED: Name[] = ['sales', 'payments', 'credit', 'movements']

/* eslint-disable @typescript-eslint/no-explicit-any */
type Data = any

// P-70 Reports: period picker, filters, totals, table, Export Excel (export_reports). Months
// and years are Ethiopian by default (D16).
export default function Reports() {
  const { user, can } = useAuth()
  const navigate = useNavigate()
  const toast = useToast()
  const allowed = BY_ROLE[user?.role ?? 'salesperson']
  const params = useParams()
  const name = (allowed.includes(params.name as Name) ? params.name : allowed[0]) as Name
  const [period, setPeriod] = useState<PeriodValue>({ period: 'month', calendar: 'ethiopian', from: '', to: '' })
  const [filters, setFilters] = useState<Record<string, string>>({})
  const [groupBy, setGroupBy] = useState('day')
  const query = { ...(DATED.includes(name) ? periodParams(period) : {}), ...filters, ...(name === 'payments' ? { group_by: groupBy } : {}) }
  const q = useApi<Data>(`/reports/${name}/`, query)
  const setFilter = (k: string, v: string) => setFilters((f) => ({ ...f, [k]: v }))

  const exportExcel = () => download(`/reports/${name}/`, { ...query, format: 'xlsx' }, `${name}.xlsx`).catch((e) => toast.show(errorMessage(e), 'error'))

  return (
    <main className="page">
      <PageHeader title={`Reports — ${TITLES[name]}`} sub={q.data?.period_label ?? ' '}
        actions={can('export_reports') && <button type="button" className="btn btn-sec" onClick={exportExcel}>Export Excel</button>} />
      {allowed.length > 1 && (
        <div className="tabs" role="tablist">
          {allowed.map((n) => <button key={n} type="button" role="tab" aria-selected={n === name} onClick={() => { setFilters({}); navigate(`/reports/${n}`) }}>{TITLES[n]}</button>)}
        </div>
      )}
      {DATED.includes(name) && <PeriodPicker value={period} onChange={setPeriod} />}
      <ReportFilters name={name} filters={filters} setFilter={setFilter} groupBy={groupBy} setGroupBy={setGroupBy} />
      {q.isLoading || q.isPlaceholderData ? <Loading /> : q.error ? <ErrorBanner error={q.error} /> : q.data && (
        <>
          {name === 'sales' && <SalesReport d={q.data} />}
          {name === 'payments' && <PaymentsReport d={q.data} />}
          {name === 'credit' && <CreditReport d={q.data} />}
          {name === 'stock' && <StockReport d={q.data} />}
          {name === 'movements' && <MovementsReport d={q.data} />}
          {name === 'open-requests' && <OpenRequestsReport d={q.data} />}
          {name === 'unverified-payments' && <UnverifiedReport d={q.data} />}
        </>
      )}
    </main>
  )
}

function ReportFilters({ name, filters, setFilter, groupBy, setGroupBy }: { name: Name; filters: Record<string, string>; setFilter: (k: string, v: string) => void; groupBy: string; setGroupBy: (v: string) => void }) {
  const { is } = useAuth()
  const { data: locations } = useRealLocations()
  const { data: categories } = useCategories()
  const { data: accounts } = usePaymentAccounts()
  const branch = !is('salesperson') && ['sales', 'payments'].includes(name) && (
    <Field label="Branch">{(id) => (
      <select id={id} className="inp" value={filters.branch ?? ''} onChange={(e) => setFilter('branch', e.target.value)}>
        <option value="">All branches</option>{locations?.filter((l) => l.can_sell).map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
      </select>
    )}</Field>
  )
  const category = ['sales', 'stock'].includes(name) && (
    <Field label="Category">{(id) => (
      <select id={id} className="inp" value={filters.category ?? ''} onChange={(e) => setFilter('category', e.target.value)}>
        <option value="">All categories</option>{categories?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
      </select>
    )}</Field>
  )
  return (
    <div className="filters">
      {branch}{category}
      {name === 'payments' && <>
        <Field label="Kind">{(id) => (
          <select id={id} className="inp" value={filters.account_kind ?? ''} onChange={(e) => setFilter('account_kind', e.target.value)}>
            <option value="">Both</option><option value="organization">Organization</option><option value="personal">Personal</option>
          </select>
        )}</Field>
        <Field label="Account">{(id) => (
          <select id={id} className="inp" value={filters.account ?? ''} onChange={(e) => setFilter('account', e.target.value)}>
            <option value="">All accounts</option>{accounts?.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        )}</Field>
        <Field label="Group by">{(id) => (
          <select id={id} className="inp" value={groupBy} onChange={(e) => setGroupBy(e.target.value)}>
            <option value="day">Day</option><option value="week">Week</option><option value="month">Ethiopian month</option><option value="year">Year</option>
          </select>
        )}</Field>
      </>}
      {name === 'movements' && <>
        {!is('storekeeper') && (
          <Field label="Location">{(id) => (
            <select id={id} className="inp" value={filters.location ?? ''} onChange={(e) => setFilter('location', e.target.value)}>
              <option value="">All locations</option>{locations?.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          )}</Field>
        )}
        <Field label="Type">{(id) => (
          <select id={id} className="inp" value={filters.type ?? ''} onChange={(e) => setFilter('type', e.target.value)}>
            <option value="">All types</option>{MOVEMENT_TYPES.map((t) => <option key={t} value={t}>{label(t)}</option>)}
          </select>
        )}</Field>
      </>}
    </div>
  )
}

const Tile = ({ title, value, sub, dark }: { title: React.ReactNode; value: React.ReactNode; sub?: React.ReactNode; dark?: boolean }) => (
  <div className={dark ? 'tile tile-dark' : 'tile'}><span className="lbl">{title}</span><span className="tile-value">{value}</span>{sub && <span className="sub">{sub}</span>}</div>
)

function Bars({ rows, nameKey, title }: { rows: Data[]; nameKey: string; title: string }) {
  const max = Math.max(1, ...rows.map((r) => Number(r.sales)))
  return (
    <Card title={title}>
      {rows.length === 0 ? <Empty title="No sales" /> : rows.map((r) => (
        <div key={r[nameKey]} className="stack" style={{ gap: 6 }}>
          <div className="spread"><span>{r[nameKey]} <span className="sub">{r.transactions} sales</span></span><span className="num" style={{ fontWeight: 600 }}>{money(r.sales)}</span></div>
          <div className="bar"><div style={{ width: `${(Number(r.sales) / max) * 100}%` }} /></div>
        </div>
      ))}
    </Card>
  )
}

function SalesReport({ d }: { d: Data }) {
  const { is } = useAuth()
  return (
    <>
      <div className="grid-tiles">
        <Tile dark title="Net sales" value={money(d.net_sales)} sub={`${d.transactions} sales · ETB`} />
        <Tile title="Sales" value={money(d.sales)} sub={`returns ${money(d.returns)}`} />
        {d.paid !== undefined && <Tile title="Paid" value={money(d.paid)} sub={`${pct(Number(d.paid), Number(d.sales))}% of these sales`} />}
        {d.credit !== undefined && <Tile title="Still owed (credit)" value={money(d.credit)} />}
        <Tile title="Official receipt" value={money(d.official_receipt)} sub={`without receipt ${money(d.no_receipt)}`} />
      </div>
      <div className="grid-tiles">
        <div className="tile"><KindBadge kind="organization" /><span className="tile-value">{money(d.received.organization)}</span><span className="sub">received</span></div>
        <div className="tile"><KindBadge kind="personal" /><span className="tile-value">{d.received.personal === null ? '—' : money(d.received.personal)}</span><span className="sub">received</span></div>
        <Tile title="Combined" value={d.received.combined === null ? '—' : money(d.received.combined)} sub="received" />
      </div>
      {!is('salesperson') && <div className="grid-cards"><Bars rows={d.by_branch} nameKey="branch" title="By branch" /><Bars rows={d.by_salesperson} nameKey="salesperson" title="By salesperson" /></div>}
      {d.by_month && (
        <Card title="By month">
          <div style={{ overflowX: 'auto' }}>
            <table className="tbl"><thead><tr><th>Month</th><th className="r">Sales</th><th className="r">Returns</th><th className="r">Net</th><th className="r">Transactions</th></tr></thead>
              <tbody>{d.by_month.map((m: Data) => <tr key={m.month}><td>{m.label}</td><td className="r">{money(m.sales)}</td><td className="r">{money(m.returns)}</td><td className="r" style={{ fontWeight: 600 }}>{money(m.net_sales)}</td><td className="r">{m.transactions}</td></tr>)}</tbody>
            </table>
          </div>
        </Card>
      )}
      <Card title="Products sold">
        {d.products.length === 0 ? <Empty title="Nothing sold in this period" /> : (
          <div style={{ overflowX: 'auto' }}>
            <table className="tbl"><thead><tr><th>#</th><th>Product</th><th className="r">Qty</th><th className="r">Sales</th></tr></thead>
              <tbody>{d.products.map((p: Data, i: number) => <tr key={p.code}><td className="sub">{i + 1}</td><td><span className="mono" style={{ fontWeight: 600 }}>{p.code}</span> {p.name}</td><td className="r">{p.qty}</td><td className="r">{money(p.sales)}</td></tr>)}</tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}

function PaymentsReport({ d }: { d: Data }) {
  return (
    <>
      <div className="grid-tiles">
        <div className="tile"><KindBadge kind="organization" /><span className="tile-value">{money(d.totals.organization)}</span></div>
        <div className="tile"><KindBadge kind="personal" /><span className="tile-value">{d.totals.personal === null ? '—' : money(d.totals.personal)}</span></div>
        <Tile dark title="Combined" value={d.totals.combined === null ? '—' : money(d.totals.combined)} sub="ETB" />
      </div>
      <Card title="By period">
        <div style={{ overflowX: 'auto' }}>
          <table className="tbl"><thead><tr><th>Period</th><th className="r">Organization</th><th className="r">Personal</th><th className="r">Combined</th></tr></thead>
            <tbody>{d.by_period.map((r: Data) => <tr key={r.period}><td>{r.label}</td><td className="r">{money(r.organization)}</td><td className="r">{r.personal === null ? '—' : money(r.personal)}</td><td className="r" style={{ fontWeight: 600 }}>{r.combined === null ? '—' : money(r.combined)}</td></tr>)}</tbody>
          </table>
        </div>
      </Card>
      <Card title="Payments">
        {d.payments.length === 0 ? <Empty title="No payments in this period" /> : (
          <div style={{ overflowX: 'auto' }}>
            <table className="tbl"><thead><tr><th>Payment</th><th>Date</th><th>Customer</th><th className="r">Amount</th><th>Account</th><th>Receipt</th><th>Status</th><th>Recorded by</th></tr></thead>
              <tbody>{d.payments.map((p: Data) => <tr key={p.number}><td><DocLink number={p.number} /></td><td>{p.date_ec}</td><td>{p.customer}</td><td className="r" style={{ fontWeight: 600 }}>{money(p.amount)}</td><td><span className="row" style={{ gap: 6 }}><KindBadge kind={p.kind} short />{p.account}</span></td><td className="mono">{p.receipt_number ?? '—'}</td><td><StatusChip kind="payment" value={p.status} /></td><td>{p.recorded_by}</td></tr>)}</tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}

function CreditReport({ d }: { d: Data }) {
  return (
    <>
      <div className="grid-tiles">
        <Tile dark title="Total outstanding" value={money(d.outstanding_total)} sub="ETB owed now" />
        <Tile title="Credit collected" value={money(d.credit_collected)} sub="in this period, for older sales" />
      </div>
      <Card title="Outstanding per customer · aged by days">
        {d.customers.length === 0 ? <Empty title="Nobody owes anything 👍" /> : (
          <div style={{ overflowX: 'auto' }}>
            <table className="tbl"><thead><tr><th>Customer</th><th>Phone</th><th>City</th><th className="r">Limit</th><th className="r">0–30</th><th className="r">31–60</th><th className="r">61–90</th><th className="r">90+</th><th className="r">Outstanding</th></tr></thead>
              <tbody>{d.customers.map((c: Data) => (
                <tr key={c.customer + c.phone}>
                  <td><strong>{c.customer}</strong>{c.shop_name && <div className="sub">{c.shop_name}</div>}</td><td className="mono">{c.phone || '—'}</td><td>{c.city || '—'}</td>
                  <td className="r">{c.credit_limit ? money(c.credit_limit) : '—'}</td>
                  <td className="r">{money(c['0_30'])}</td><td className="r">{money(c['31_60'])}</td>
                  <td className="r" style={Number(c['61_90']) ? { color: 'var(--amber-fg)' } : undefined}>{money(c['61_90'])}</td>
                  <td className="r" style={Number(c.over_90) ? { color: 'var(--red-fg)', fontWeight: 600 } : undefined}>{money(c.over_90)}</td>
                  <td className="r" style={{ fontWeight: 700 }}>{money(c.outstanding)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}

function StockReport({ d }: { d: Data }) {
  const cols: string[] = d.locations.filter((c: string) => c !== 'TRANSIT')
  return (
    <div className="tw">
      <table className="tbl">
        <thead><tr><th>Product</th>{cols.map((c) => <th key={c} className="r">{c}</th>)}<th className="r">In transit</th><th className="r">Total</th><th className="r">Display</th><th className="r">Damaged</th><th className="r">Sellable</th><th className="r">Min</th></tr></thead>
        <tbody>{d.products.map((p: Data) => (
          <tr key={p.code} className={p.low_stock ? 'hl' : undefined}>
            <td><span className="mono" style={{ fontWeight: 600 }}>{p.code}</span> {p.name}</td>
            {cols.map((c) => <td key={c} className="r">{p.stock[c]}</td>)}
            <td className="r">{p.in_transit}</td><td className="r" style={{ fontWeight: 700 }}>{p.total}</td><td className="r">{p.display}</td><td className="r">{p.damaged}</td>
            <td className="r" style={p.low_stock ? { color: 'var(--amber-fg)', fontWeight: 700 } : { fontWeight: 600 }}>{p.total_new}</td><td className="r sub">{p.min_stock}</td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  )
}

function MovementsReport({ d }: { d: Data }) {
  return (
    <div className="tw">
      {d.movements.length === 0 ? <Empty title="No movements in this period" /> : (
        <table className="tbl"><thead><tr><th>Date</th><th>Number</th><th>Type</th><th>Condition</th><th>Product</th><th className="r">Qty</th><th>From</th><th>To</th><th>Customer</th><th>Transaction</th><th>Person</th></tr></thead>
          <tbody>{d.movements.map((m: Data) => (
            <tr key={m.number}><td>{m.date_ec}</td><td className="mono" style={{ fontSize: 13 }}>{m.number}</td><td>{label(m.type)}</td><td><CondTag condition={m.condition} /></td><td className="mono">{m.product}</td><td className="r" style={{ fontWeight: 600 }}>{m.qty}</td><td>{m.from ?? '—'}</td><td>{m.to ?? '—'}</td><td>{m.customer ?? '—'}</td><td><DocLink number={m.transaction || m.reference} /></td><td>{m.person}</td></tr>
          ))}</tbody>
        </table>
      )}
    </div>
  )
}

function OpenRequestsReport({ d }: { d: Data }) {
  return (
    <div className="tw">
      {d.requests.length === 0 ? <Empty title="No open requests 👍" /> : (
        <table className="tbl"><thead><tr><th>Request</th><th>Status</th><th>Branch → source</th><th>Customer</th><th>Salesperson</th><th>Created</th><th className="r">Waiting</th><th className="r">Units left</th></tr></thead>
          <tbody>{d.requests.map((r: Data) => (
            <tr key={r.number} className={r.waiting_hours > 24 ? 'hl' : undefined}>
              <td><Link className="mono" to={`/stock-requests?search=${r.number}`}>{r.number}</Link></td><td><StatusChip kind="request" value={r.status} /></td>
              <td>{r.branch} → {r.source}</td><td>{r.customer ?? '—'}</td><td>{r.salesperson}</td><td>{r.date_ec}</td>
              <td className="r" style={r.waiting_hours > 24 ? { color: 'var(--amber-fg)', fontWeight: 600 } : undefined}>{r.waiting_hours < 48 ? `${r.waiting_hours} h` : `${Math.round(r.waiting_hours / 24)} days`}</td>
              <td className="r">{r.units_remaining}</td>
            </tr>
          ))}</tbody>
        </table>
      )}
    </div>
  )
}

function UnverifiedReport({ d }: { d: Data }) {
  return (
    <>
      <div className="grid-tiles"><Tile dark title="Waiting for the accountant" value={d.count} sub={`${money(d.total)} ETB`} /></div>
      <div className="tw">
        {d.payments.length === 0 ? <Empty title="Nothing to verify 👍" /> : (
          <table className="tbl"><thead><tr><th>Payment</th><th>Paid</th><th>Customer</th><th className="r">Amount</th><th>Account</th><th>Receipt</th><th>Recorded by</th></tr></thead>
            <tbody>{d.payments.map((p: Data) => (
              <tr key={p.number}><td><DocLink number={p.number} to={p.id ? `/payments/${p.id}` : undefined} /></td><td>{p.date_ec}</td><td>{p.customer}</td><td className="r" style={{ fontWeight: 600 }}>{money(p.amount)}</td><td><span className="row" style={{ gap: 6 }}><KindBadge kind={p.kind} short />{p.account}</span></td><td className="mono">{p.receipt_number ?? '—'}</td><td>{p.recorded_by}</td></tr>
            ))}</tbody>
          </table>
        )}
      </div>
    </>
  )
}
