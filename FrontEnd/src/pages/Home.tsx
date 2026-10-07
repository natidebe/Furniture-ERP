import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useAction, useApi, useLocations } from '../api/hooks'
import type { Dashboard, DashboardRequest, ProductStock } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { ConfirmDialog, ReasonDialog } from '../components/Dialog'
import { ProductPicker } from '../components/pickers'
import type { PickedProduct } from '../components/pickers'
import { Card, CondTag, DocLink, Empty, ErrorBanner, KindBadge, Loading, Money, PageHeader, StatusChip } from '../components/ui'
import { formatBoth, isoDate, todayAddis } from '../lib/ethiopian'
import { money, pct } from '../lib/format'
import { label } from '../lib/labels'

// P-02 — short and actionable; every tile links to its filtered list. One call: GET /dashboard/.
export default function Home() {
  const { user } = useAuth()
  const { data, isLoading, error } = useApi<Dashboard>('/dashboard/', undefined, { refetchInterval: 60_000 })
  if (isLoading) return <div className="page"><Loading /></div>
  if (error || !data) return <div className="page"><ErrorBanner error={error} /></div>
  if (user?.role === 'salesperson') return <SalesHome data={data} />
  if (user?.role === 'storekeeper') return <StoreHome data={data} />
  return <OfficeHome data={data} admin={user?.role === 'admin'} />
}

function useHomeName() {
  const { user } = useAuth()
  const { data: locations } = useLocations()
  return locations?.find((l) => l.id === user?.home_location)?.name
}

const todayText = () => formatBoth(isoDate(todayAddis()))

// ---------------------------------------------------------------- salesperson

function SalesHome({ data }: { data: Dashboard }) {
  const where = useHomeName()
  const s = data.sales_today!
  const waiting = data.waiting_for_payment!
  const arriving = data.transfers_arriving!
  const held = data.held_for_customers!
  const requests = data.open_requests!
  return (
    <main className="page">
      <PageHeader title="Home" sub={`${todayText()}${where ? ` · ${where}` : ''}`}
        actions={<><Link className="btn btn-sec" to="/stock-requests/new">New stock request</Link><Link className="btn btn-pri" to="/sales/new">New sale</Link></>} />
      <QuickStock />
      <div className="grid-tiles">
        <Link className="tile tile-dark" to={`/sales?from=${isoDate(todayAddis())}&to=${isoDate(todayAddis())}`}><span className="lbl">My sales today</span><span className="tile-value">{money(s.sales)}</span><span className="sub">{s.transactions} sales · ETB</span></Link>
        <Link className="tile" to="/sales?owing=true"><span className="lbl">Waiting for payment</span><span className="tile-value">{waiting.count}</span><span className="sub">of my sales</span></Link>
        <Link className="tile" to="/stock-requests?open=true"><span className="lbl">Open stock requests</span><span className="tile-value">{requests.count}</span><span className="sub">at my branch</span></Link>
        <Link className="tile" to="/transfers?tab=incoming"><span className="lbl">Arriving</span><span className="tile-value">{arriving.count}</span><span className="sub">transfers to receive</span></Link>
        <div className="tile"><span className="lbl">Held for customers</span><span className="tile-value">{held.count}</span><span className="sub">lines waiting for handover</span></div>
      </div>
      <div className="grid-cards" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(520px, 100%), 1fr))' }}>
        <Card title="My sales waiting for payment" actions={<Link to="/sales?owing=true" style={{ fontSize: 13 }}>All waiting</Link>}>
          {waiting.items.length === 0 ? <Empty title="Nothing waiting" hint="Every sale is paid." /> : (
            <div style={{ overflowX: 'auto' }}>
              <table className="tbl">
                <thead><tr><th>Sale</th><th>Customer</th><th className="r">Total</th><th>Payment</th><th /></tr></thead>
                <tbody>
                  {waiting.items.map((o) => (
                    <tr key={o.id}>
                      <td><DocLink number={o.number} to={`/sales/${o.id}`} /><div className="sub">{o.date_ec}</div></td>
                      <td>{o.customer}</td>
                      <td className="r"><Money value={o.total} /></td>
                      <td><StatusChip kind="orderPayment" value={o.payment_status} /></td>
                      <td className="r"><Link className="btn btn-sec btn-sm" to={`/payments/new?order=${o.id}`}>Record payment</Link></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
        <div className="stack" style={{ gap: 20 }}>
          <Card title={`Arriving${where ? ` at ${where}` : ''}`} actions={<Link to="/transfers?tab=incoming" style={{ fontSize: 13 }}>Transfers</Link>}>
            {arriving.items.length === 0 ? <Empty title="Nothing on the way" /> : arriving.items.map((t) => (
              <div className="card-row" key={t.id}>
                <div className="grow stack" style={{ gap: 2 }}>
                  <div className="row"><DocLink number={t.number} to={`/transfers/${t.id}`} /><StatusChip kind="transfer" value={t.status} /></div>
                  <span className="sub">From {t.from}{t.transaction && <> · for <span className="mono">{t.transaction}</span></>}</span>
                </div>
                <Link className="btn btn-pri btn-sm" to={`/transfers/${t.id}`}>Receive</Link>
              </div>
            ))}
          </Card>
          <Card title="Held here for my customers">
            {held.items.length === 0 ? <Empty title="Nothing held" /> : held.items.map((h) => (
              <div className="card-row" key={`${h.order_id}-${h.product}`}>
                <div className="grow stack" style={{ gap: 2 }}>
                  <span style={{ fontWeight: 600 }}>{h.customer}</span>
                  <span className="sub"><span className="mono">{h.order}</span> · {h.qty} × {h.product}</span>
                </div>
                <Link className="btn btn-sec btn-sm" to={`/sales/${h.order_id}`}>Hand over</Link>
              </div>
            ))}
          </Card>
          <Card title="Open stock requests" actions={<Link to="/stock-requests" style={{ fontSize: 13 }}>All</Link>}>
            {requests.items.length === 0 ? <Empty title="No open requests" /> : requests.items.map((r) => (
              <div className="card-row" key={r.id}>
                <div className="grow stack" style={{ gap: 2 }}>
                  <div className="row"><DocLink number={r.number} to={`/stock-requests/${r.id}`} /><StatusChip kind="request" value={r.status} /></div>
                  <span className="sub">{r.lines}{r.customer && ` · ${r.customer}`}</span>
                </div>
              </div>
            ))}
          </Card>
        </div>
      </div>
    </main>
  )
}

/** "Check stock and price": a product code → the stock card. */
function QuickStock() {
  const [picked, setPicked] = useState<PickedProduct | null>(null)
  const stock = useApi<ProductStock>(picked ? `/products/${picked.id}/stock/` : null)
  return (
    <section className="card card-pad">
      <label className="fld-label" htmlFor="quick-stock">Check stock and price</label>
      <div style={{ maxWidth: 520 }}><ProductPicker id="quick-stock" onPick={setPicked} stockAt={['PIA', 'DEN', 'PAW']} /></div>
      {picked && (
        <div className="row" style={{ alignItems: 'flex-start', gap: 24 }}>
          <div className="stack" style={{ gap: 4, minWidth: 220 }}>
            <Link to={`/products/${picked.id}`} style={{ fontWeight: 600, fontSize: 16 }}><span className="mono">{picked.code}</span> {picked.name}</Link>
            <span className="num" style={{ fontWeight: 600 }}>{money(picked.selling_price)} ETB{picked.wholesale_price && <span className="sub"> · Wholesale {money(picked.wholesale_price)}</span>}</span>
            <span className="sub">{picked.category_name} · {picked.unit_symbol} · min {picked.min_stock}</span>
          </div>
          {stock.data && (
            <div className="row" style={{ gap: 18 }}>
              {stock.data.locations.map((l) => {
                const cell = stock.data!.stock[l.code]
                return (
                  <div key={l.code} className="stack" style={{ gap: 2 }}>
                    <span className="lbl">{l.code === 'TRANSIT' ? 'In transit' : l.name}</span>
                    <span style={{ fontSize: 22, fontWeight: 600 }}>{cell?.on_hand ?? 0}</span>
                    <span className="sub">{cell && cell.available !== cell.on_hand ? `${cell.available} free` : ' '}</span>
                  </div>
                )
              })}
              <div className="stack" style={{ gap: 2 }}><span className="lbl">Total</span><span style={{ fontSize: 22, fontWeight: 700 }}>{stock.data.total}</span><span className="sub">{stock.data.total_new} sellable</span></div>
            </div>
          )}
        </div>
      )}
    </section>
  )
}

// ---------------------------------------------------------------- storekeeper

function StoreHome({ data }: { data: Dashboard }) {
  const where = useHomeName()
  const queue = data.request_queue!
  const count = (status: string) => queue.by_status?.[status] ?? queue.items.filter((r) => r.status === status).length
  const low = data.low_stock!
  return (
    <main className="page">
      <PageHeader title="Requests waiting" sub={`${todayText()}${where ? ` · ${where}` : ''}`}
        actions={<><Link className="btn btn-sec" to="/goods-receipts?new=1">New goods receipt</Link><Link className="btn btn-sec" to="/adjustments?new=1">Propose adjustment</Link></>} />
      <div className="grid-tiles">
        <Link className="tile" to="/stock-requests?status=pending"><StatusChip kind="request" value="pending" /><span className="tile-value">{count('pending')}</span><span className="sub">Acknowledge or reject</span></Link>
        <Link className="tile" to="/stock-requests?status=acknowledged"><StatusChip kind="request" value="acknowledged" /><span className="tile-value">{count('acknowledged')}</span><span className="sub">Ready to release</span></Link>
        <Link className="tile" to="/stock-requests?status=partially_released"><StatusChip kind="request" value="partially_released" /><span className="tile-value">{count('partially_released')}</span><span className="sub">Release the rest or close</span></Link>
        <Link className="tile" to="/stock/low"><span className="chip c-amber" style={{ alignSelf: 'flex-start' }}>Low stock</span><span className="tile-value">{low.count}</span><span className="sub">Products below minimum</span></Link>
      </div>
      <div className="grid-cards" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(520px, 100%), 1fr))' }}>
        <section className="stack" style={{ gap: 12 }} aria-label="Request queue">
          {queue.items.length === 0 ? <div className="card"><Empty title="No open requests 👍" hint="New requests from the branches appear here." /></div>
            : queue.items.map((r) => <QueueCard key={r.id} r={r} />)}
          {queue.count > queue.items.length && <Link to="/stock-requests?open=true" className="btn btn-sec">All {queue.count} open requests</Link>}
        </section>
        <div className="stack" style={{ gap: 20 }}>
          <Card title="Low stock" actions={<Link to="/stock/low" style={{ fontSize: 13 }}>All</Link>}>
            {low.items.length === 0 ? <Empty title="Nothing below minimum" /> : low.items.map((l) => (
              <div className="card-row" key={l.id}>
                <Link className="mono" to={`/products/${l.id}`} style={{ fontWeight: 600, width: 72 }}>{l.code}</Link>
                <span className="grow muted">{l.name}</span>
                <span style={{ fontWeight: 600, color: 'var(--amber-fg)' }}>{l.sellable}</span><span className="sub">/ min {l.min_stock}</span>
              </div>
            ))}
          </Card>
          <Card title="Sent, not yet received" actions={<Link to="/transfers?tab=outgoing" style={{ fontSize: 13 }}>Transfers</Link>}>
            {data.transfers_not_received!.items.length === 0 ? <Empty title="Everything sent has arrived" /> : data.transfers_not_received!.items.map((t) => (
              <div className="card-row" key={t.id}>
                <DocLink number={t.number} to={`/transfers/${t.id}`} /><StatusChip kind="transfer" value={t.status} />
                <span className="sub grow">To {t.to} · since {t.date_ec}</span>
              </div>
            ))}
          </Card>
          <Card title="Recent movements" actions={<Link to="/movements" style={{ fontSize: 13 }}>All</Link>}>
            {data.recent_movements!.items.length === 0 ? <Empty title="No movements yet" /> : data.recent_movements!.items.map((m) => (
              <div className="card-row" key={m.id}>
                <span className="sub" style={{ width: 110 }}>{label(m.type)}</span>
                <span className="grow"><span className="mono">{m.product}</span> {m.from ?? '—'} → {m.to ?? '—'} {m.condition !== 'new' && <CondTag condition={m.condition} />}</span>
                <span style={{ fontWeight: 600 }}>{m.qty}</span>
              </div>
            ))}
          </Card>
        </div>
      </div>
    </main>
  )
}

function QueueCard({ r }: { r: DashboardRequest }) {
  const navigate = useNavigate()
  const [dialog, setDialog] = useState<'ack' | 'reject' | null>(null)
  const ack = useAction(() => api.post(`/stock-requests/${r.id}/acknowledge/`), { success: `${r.number} acknowledged.` })
  const reject = useAction((reason: string) => api.post(`/stock-requests/${r.id}/reject/`, { reason }), { success: `${r.number} rejected.`, toastErrors: false })
  const isNew = r.status === 'pending' && Date.now() - new Date(r.created_at).getTime() < 30 * 60_000
  return (
    <article className="card" style={{ padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="row">
        <DocLink number={r.number} to={`/stock-requests/${r.id}`} strong />
        <StatusChip kind="request" value={r.status} />
        {isNew && <span className="tag" style={{ background: 'var(--gold)', color: 'var(--sidebar)' }}>NEW</span>}
        <span className="sub" style={{ marginLeft: 'auto' }}>{r.date_ec}</span>
      </div>
      <div className="row" style={{ gap: 24 }}>
        <div className="stack" style={{ gap: 2 }}><span className="lbl">From</span><span>{r.branch}</span></div>
        <div className="stack" style={{ gap: 2 }}><span className="lbl">Customer / ref</span><span>{r.customer ?? '—'}</span></div>
        <div className="stack" style={{ gap: 2 }}><span className="lbl">Salesperson</span><span>{r.salesperson}</span></div>
      </div>
      <div className="spread">
        <span className="mono" style={{ fontWeight: 600 }}>{r.lines}</span>
        <div className="row">
          {r.status === 'pending' && <>
            <button type="button" className="btn btn-dan btn-sm" onClick={() => setDialog('reject')}>Reject…</button>
            <button type="button" className="btn btn-pri btn-sm" onClick={() => setDialog('ack')}>Acknowledge</button>
          </>}
          {(r.status === 'acknowledged' || r.status === 'partially_released') && (
            <button type="button" className="btn btn-pri btn-sm" onClick={() => navigate(`/stock-requests/${r.id}/release`)}>Release</button>
          )}
        </div>
      </div>
      {dialog === 'ack' && <ConfirmDialog title="Acknowledge request" message={<>Acknowledge <span className="mono">{r.number}</span> from {r.branch} ({r.lines})? The branch is told you are on it.</>}
        confirmLabel="Acknowledge" onConfirm={() => ack.mutateAsync(undefined)} onClose={() => setDialog(null)} />}
      {dialog === 'reject' && <ReasonDialog title="Reject request" message={<>Reject <span className="mono">{r.number}</span>? The reserved stock is freed and {r.salesperson} is told.</>}
        confirmLabel="Reject request" onConfirm={(reason) => reject.mutateAsync(reason)} onClose={() => setDialog(null)} />}
    </article>
  )
}

// ---------------------------------------------------------------- accountant / admin

function OfficeHome({ data, admin }: { data: Dashboard; admin: boolean }) {
  const t = data.today!
  const verify = data.payments_to_verify!
  const { can } = useAuth()
  const maxBranch = Math.max(1, ...(t.by_branch ?? []).map((b) => Number(b.sales)))
  const maxPerson = Math.max(1, ...(t.by_salesperson ?? []).map((b) => Number(b.sales)))
  return (
    <main className="page">
      <PageHeader title="Today" sub={`${t.period_label} · all branches`}
        actions={<><Link className="btn btn-sec" to="/reports">Reports</Link><Link className="btn btn-pri" to="/sales/new">New sale</Link></>} />
      <div className="grid-tiles">
        <Link className="tile tile-dark" to="/reports/sales"><span className="lbl">Sales</span><span className="tile-value">{money(t.sales)}</span><span className="sub">{t.transactions} sales · ETB</span></Link>
        <Link className="tile" to="/reports/sales"><span className="lbl">Paid</span><span className="tile-value">{money(t.paid)}</span><span className="sub">{pct(Number(t.paid), Number(t.sales))}% of today's sales</span></Link>
        <Link className="tile" to="/reports/credit"><span className="lbl">Still owed (credit)</span><span className="tile-value">{money(t.credit)}</span><span className="sub">from today's sales</span></Link>
        <Link className="tile" to="/payments?account_kind=organization"><KindBadge kind="organization" /><span className="tile-value">{money(t.received.organization)}</span><span className="sub">Received today</span></Link>
        <Link className="tile" to="/payments?account_kind=personal"><KindBadge kind="personal" /><span className="tile-value">{t.received.personal === null ? '—' : money(t.received.personal)}</span><span className="sub">Received today</span></Link>
      </div>
      <div className="grid-cards">
        <Card title={<>Payments to verify {verify.count > 0 && <span className="chip c-amber" style={{ marginLeft: 6 }}>{verify.count} · {money(verify.total)}</span>}</>}
          actions={<Link to="/payments/verify" style={{ fontSize: 13 }}>Open queue</Link>}>
          {verify.items.length === 0 ? <Empty title="Nothing to verify" hint="Payments recorded by salespeople appear here." /> : verify.items.map((p) => (
            <VerifyRow key={p.number} p={p} canVerify={can('verify_payments')} />
          ))}
        </Card>
        <div className="stack" style={{ gap: 20 }}>
          <Card title="Adjustments waiting for approval" actions={<Link to="/adjustments?status=proposed" style={{ fontSize: 13 }}>All</Link>}>
            {data.adjustments_to_approve!.items.length === 0 ? <Empty title="Nothing to approve" /> : data.adjustments_to_approve!.items.map((a) => (
              <div className="card-row" key={a.id}>
                <div className="grow stack" style={{ gap: 2 }}>
                  <span><Link className="mono" to="/adjustments?status=proposed">{a.number}</Link> · {a.location} · <span className="mono" style={{ fontWeight: 600 }}>{a.product}</span> <strong style={{ color: a.qty_delta < 0 ? 'var(--red-fg)' : 'var(--green-fg)' }}>{a.qty_delta > 0 ? '+' : ''}{a.qty_delta}</strong> <CondTag condition={a.condition} /></span>
                  <span className="sub">{label(a.reason)} · proposed by {a.proposed_by}</span>
                </div>
              </div>
            ))}
          </Card>
          <Card title="Transfers with shortages · last 30 days" actions={<Link to="/transfers" style={{ fontSize: 13 }}>Transfers</Link>}>
            {data.transfers_with_shortages!.items.length === 0 ? <Empty title="No shortages" /> : data.transfers_with_shortages!.items.map((s) => (
              <div className="card-row" key={s.id}>
                <DocLink number={s.number} to={`/transfers/${s.id}`} />
                <span className="grow muted">{s.from} → {s.to} · {s.discrepancy_note}</span>
                <span className="chip c-amber">Short</span>
              </div>
            ))}
          </Card>
          <Card title="Customers over their limit" actions={<Link to="/customers?over_limit=true" style={{ fontSize: 13 }}>Customers</Link>}>
            {data.customers_over_limit!.items.length === 0 ? <Empty title="Nobody over their limit" /> : data.customers_over_limit!.items.map((c) => (
              <div className="card-row" key={c.id}>
                <Link to={`/customers/${c.id}`} className="grow" style={{ fontWeight: 600 }}>{c.name}</Link>
                <span className="num"><strong>{money(c.outstanding)}</strong> <span className="sub">/ {c.credit_allowed ? `limit ${money(c.credit_limit)}` : 'no credit'}</span></span>
                <span className="chip c-amber">Over limit</span>
              </div>
            ))}
          </Card>
        </div>
      </div>
      {admin && (
        <div className="grid-cards" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(300px, 100%), 1fr))' }}>
          <Card title="Today by branch">
            {(t.by_branch ?? []).length === 0 ? <Empty title="No sales yet today" /> : t.by_branch!.map((b) => (
              <div key={b.branch} className="stack" style={{ gap: 6 }}>
                <div className="spread"><span>{b.branch} <span className="sub">{b.transactions} sales</span></span><span className="num" style={{ fontWeight: 600 }}>{money(b.sales)}</span></div>
                <div className="bar"><div style={{ width: `${(Number(b.sales) / maxBranch) * 100}%` }} /></div>
              </div>
            ))}
          </Card>
          <Card title="Today by salesperson">
            {(t.by_salesperson ?? []).length === 0 ? <Empty title="No sales yet today" /> : t.by_salesperson!.map((b) => (
              <div key={b.salesperson} className="stack" style={{ gap: 6 }}>
                <div className="spread"><span>{b.salesperson} <span className="sub">{b.transactions}</span></span><span className="num" style={{ fontWeight: 600 }}>{money(b.sales)}</span></div>
                <div className="bar"><div style={{ width: `${(Number(b.sales) / maxPerson) * 100}%` }} /></div>
              </div>
            ))}
          </Card>
          <Card title="Low stock" actions={<Link to="/stock/low" style={{ fontSize: 13 }}>All {data.low_stock!.count}</Link>}>
            {data.low_stock!.items.length === 0 ? <Empty title="Nothing below minimum" /> : data.low_stock!.items.map((l) => (
              <div className="card-row" key={l.id}>
                <Link className="mono" to={`/products/${l.id}`} style={{ fontWeight: 600, width: 72 }}>{l.code}</Link>
                <span className="grow muted">{l.name}</span>
                <span style={{ fontWeight: 600, color: 'var(--amber-fg)' }}>{l.sellable}</span><span className="sub">/ min {l.min_stock}</span>
              </div>
            ))}
          </Card>
        </div>
      )}
    </main>
  )
}

type VerifyItem = NonNullable<Dashboard['payments_to_verify']>['items'][number]

/** One unverified payment with a one-click Verify. */
function VerifyRow({ p, canVerify }: { p: VerifyItem; canVerify: boolean }) {
  const [confirm, setConfirm] = useState(false)
  const verify = useAction(() => api.post(`/payments/${p.id}/verify/`), { success: `${p.number} verified.` })
  return (
    <div className="card-row">
      <div className="grow stack" style={{ gap: 3 }}>
        <div className="row" style={{ gap: 8 }}><DocLink number={p.number} to={`/payments/${p.id}`} /><KindBadge kind={p.kind} /><span className="sub">{p.account}</span></div>
        <span className="sub" style={{ fontSize: 13 }}>{p.customer} · by {p.recorded_by} · {p.date_ec}</span>
      </div>
      <Money value={p.amount} strong />
      {canVerify && <button type="button" className="btn btn-pri btn-sm" onClick={() => setConfirm(true)}>Verify</button>}
      {confirm && <ConfirmDialog title="Verify payment" message={<>Verify <span className="mono">{p.number}</span>: <strong>{money(p.amount)} ETB</strong> to {p.account} ({p.kind === 'personal' ? 'Personal' : 'Organization'}){p.receipt_number ? `, receipt ${p.receipt_number}` : ''}? Check it is on the statement first.</>}
        confirmLabel="Verify" onConfirm={() => verify.mutateAsync(undefined)} onClose={() => setConfirm(false)} />}
    </div>
  )
}
