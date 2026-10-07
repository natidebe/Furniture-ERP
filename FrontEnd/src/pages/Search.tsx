import { useEffect } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useApi, useRealLocations } from '../api/hooks'
import type { Paginated, SearchResult, User } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { EthDatePicker } from '../components/EthDatePicker'
import { Card, DocLink, Empty, ErrorBanner, EthDate, Field, KindBadge, Loading, Money, PageHeader, StatusChip } from '../components/ui'
import { money } from '../lib/format'
import { label } from '../lib/labels'

const EXACT_ROUTE: Record<string, (id: number) => string> = {
  product: (id) => `/products/${id}`,
  order: (id) => `/sales/${id}`,
  stock_request: (id) => `/stock-requests/${id}`,
  payment: (id) => `/payments/${id}`,
  delivery_note: (id) => `/delivery-notes/${id}`,
}

// P-04 Search results. The top-bar search takes anything: a product code jumps to its card,
// a document number straight to the document.
export default function Search() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const { is } = useAuth()
  const q = params.get('q') ?? ''
  const filters = { salesperson: params.get('salesperson') ?? '', branch: params.get('branch') ?? '', from: params.get('from') ?? '', to: params.get('to') ?? '' }
  const result = useApi<SearchResult>(q ? '/search/' : null, { q, ...filters })
  const { data: locations } = useRealLocations()
  const salespeople = useApi<Paginated<User>>(is('admin') ? '/users/' : null, { role: 'salesperson', page_size: 100 })
  const set = (key: string, value: string) => setParams((p) => { const n = new URLSearchParams(p); if (value) n.set(key, value); else n.delete(key); return n }, { replace: true })

  // When the API finds an exact document (not a product), open it directly.
  useEffect(() => {
    const exact = result.data?.exact
    if (exact && exact.kind !== 'product' && exact.kind !== 'delivery_note' && result.data?.query === q) {
      navigate(EXACT_ROUTE[exact.kind](exact.id), { replace: true })
    }
  }, [result.data, q, navigate])

  const r = result.data
  const total = r ? r.products.length + r.customers.length + r.orders.length + r.delivery_notes.length + r.stock_requests.length + r.payments.length : 0
  return (
    <main className="page">
      <PageHeader title={q ? <>Results for “{q}”</> : 'Search'} sub={r ? `${total} found` : ' '} />
      <div className="filters">
        {!is('salesperson') && (
          <Field label="Branch">{(id) => (
            <select id={id} className="inp" value={filters.branch} onChange={(e) => set('branch', e.target.value)}>
              <option value="">All branches</option>{locations?.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          )}</Field>
        )}
        {is('admin') && (
          <Field label="Salesperson">{(id) => (
            <select id={id} className="inp" value={filters.salesperson} onChange={(e) => set('salesperson', e.target.value)}>
              <option value="">Anyone</option>{salespeople.data?.results.map((u) => <option key={u.id} value={u.id}>{u.full_name || u.username}</option>)}
            </select>
          )}</Field>
        )}
        <Field label="From" style={{ flex: '0 1 240px' }}>{(id) => <EthDatePicker id={id} value={filters.from} onChange={(v) => set('from', v)} />}</Field>
        <Field label="To" style={{ flex: '0 1 240px' }}>{(id) => <EthDatePicker id={id} value={filters.to} onChange={(v) => set('to', v)} />}</Field>
      </div>
      {!q && <Empty title="Type in the search box above" hint="A product code, customer name or phone, or an SO / DN / SR / PAY number." />}
      {result.isLoading && <Loading />}
      {result.error && <ErrorBanner error={result.error} />}
      {r && total === 0 && <Empty title="Nothing found" hint="Check the spelling, or search by code, phone or document number." />}
      {r && r.products.map((p, i) => (
        <section key={p.id} className="card card-pad" style={i === 0 && r.exact?.kind === 'product' ? { borderColor: 'var(--primary)' } : undefined}>
          <div className="spread">
            <Link to={`/products/${p.id}`} style={{ fontSize: 18, fontWeight: 600 }}><span className="mono">{p.code}</span> {p.name}</Link>
            <span className="num"><strong>{money(p.selling_price)}</strong> ETB{p.wholesale_price && <span className="sub"> · Wholesale {money(p.wholesale_price)}</span>}</span>
          </div>
          <div className="row" style={{ gap: 24 }}>
            {Object.entries(p.stock).filter(([code]) => code !== 'TRANSIT').map(([code, n]) => (
              <div key={code} className="stack" style={{ gap: 2 }}><span className="lbl">{code}</span><span style={{ fontSize: 20, fontWeight: 600 }}>{n}</span></div>
            ))}
            <div className="stack" style={{ gap: 2 }}><span className="lbl">In transit</span><span style={{ fontSize: 20, fontWeight: 600, color: p.in_transit ? 'var(--link)' : undefined }}>{p.in_transit}</span></div>
            <div className="stack" style={{ gap: 2 }}><span className="lbl">Total</span><span style={{ fontSize: 20, fontWeight: 700 }}>{p.total}</span></div>
          </div>
        </section>
      ))}
      {r && r.customers.length > 0 && (
        <Card title="Customers">
          {r.customers.map((c) => (
            <div className="card-row" key={c.id}>
              <Link to={`/customers/${c.id}`} style={{ fontWeight: 600 }}>{c.name}</Link>
              <span className="grow sub">{[c.shop_name, c.phone, c.city, label(c.type)].filter(Boolean).join(' · ')}</span>
              <span className="num">owes <strong>{money(c.outstanding)}</strong></span>
            </div>
          ))}
        </Card>
      )}
      {r && r.orders.length > 0 && (
        <Card title="Sales">
          {r.orders.map((o) => (
            <div className="card-row" key={o.id}>
              <DocLink number={o.number} to={`/sales/${o.id}`} strong />
              <span className="grow">{o.customer} <span className="sub">· {o.branch} · {o.salesperson} · <EthDate value={o.created_at} time={false} /></span></span>
              <Money value={o.total} strong /><StatusChip kind="fulfilment" value={o.status} /><StatusChip kind="orderPayment" value={o.payment_status} />
            </div>
          ))}
        </Card>
      )}
      {r && r.delivery_notes.length > 0 && (
        <Card title="Delivery notes">
          {r.delivery_notes.map((n) => (
            <div className="card-row" key={n.id}>
              <span className="mono">{n.number}</span><span className="grow sub">for <span className="mono">{String(n.order)}</span> · {String(n.location)}</span>
              <Link className="btn btn-sec btn-sm" to={`/delivery-notes/${n.id}`} target="_blank">Open</Link>
            </div>
          ))}
        </Card>
      )}
      {r && r.stock_requests.length > 0 && (
        <Card title="Stock requests">
          {r.stock_requests.map((s) => (
            <div className="card-row" key={s.id}>
              <DocLink number={s.number} to={`/stock-requests/${s.id}`} strong /><span className="grow sub">{String(s.branch)}</span><StatusChip kind="request" value={String(s.status)} />
            </div>
          ))}
        </Card>
      )}
      {r && r.payments.length > 0 && (
        <Card title="Payments">
          {r.payments.map((p) => {
            const pay = p as unknown as { id: number; number: string; customer_name: string; amount: string | null; hidden: boolean; account_kind: string; status: string; receipt_number: string | null }
            return (
              <div className="card-row" key={pay.id}>
                <DocLink number={pay.number} to={`/payments/${pay.id}`} strong /><KindBadge kind={pay.account_kind} short />
                <span className="grow">{pay.customer_name}{pay.receipt_number && <span className="sub"> · receipt {pay.receipt_number}</span>}</span>
                <Money value={pay.amount} hidden={pay.hidden} strong /><StatusChip kind="payment" value={pay.status} />
              </div>
            )
          })}
        </Card>
      )}
    </main>
  )
}
