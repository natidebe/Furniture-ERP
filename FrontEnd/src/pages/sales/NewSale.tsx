import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ApiError, api, errorMessage } from '../../api/client'
import { useApi, usePaymentAccounts, useRealLocations, useSettings } from '../../api/hooks'
import type { Customer, Order, Product } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { Dialog } from '../../components/Dialog'
import { MoneyInput, QtyStepper } from '../../components/inputs'
import { CustomerPicker, ProductPicker, priceFor, useWalkInCustomer } from '../../components/pickers'
import type { PickedProduct } from '../../components/pickers'
import { Banner, Card, ErrorBanner, Field, KindBadge, Loading, PageHeader, Seg } from '../../components/ui'
import { formatBoth, isoDate, todayAddis } from '../../lib/ethiopian'
import { fromCents, money, toCents } from '../../lib/format'
import { label } from '../../lib/labels'
import { useQueryClient } from '@tanstack/react-query'
import { CustomerEditor } from '../customers/CustomerForm'

interface SaleLine {
  key: string
  product: PickedProduct
  qty: number
  source: 'branch' | 'warehouse'
  condition: 'new' | 'display' | 'damaged'
  discount: string
}

// P-40 New sale — the most-used screen; fast at the counter.
// Customer → channel → lines (price from the product, wholesale for resellers; no typed
// prices) → receipt type → pay now (optional) → confirm. A remaining balance needs credit
// within the customer's limit, unless the user has approve_credit.
export default function NewSale() {
  const { user, can, is } = useAuth()
  const [params] = useSearchParams()
  const replacesId = params.get('replaces')
  const queryClient = useQueryClient()
  const { data: locations } = useRealLocations()
  const { data: accounts } = usePaymentAccounts()
  const { data: settings } = useSettings()
  const walkIn = useWalkInCustomer()

  const [branchId, setBranchId] = useState<string>(String(user?.home_location ?? ''))
  const [channel, setChannel] = useState<'walk_in' | 'phone'>('walk_in')
  const [customer, setCustomer] = useState<Customer | null>(null)
  const [lines, setLines] = useState<SaleLine[]>([])
  const [receiptType, setReceiptType] = useState<'official' | 'none'>('none')
  const [notes, setNotes] = useState('')
  const [payOn, setPayOn] = useState(false)
  const [pay, setPay] = useState({ account: '', amount: '', method: 'cash', receipt: '' })
  const [newCustomer, setNewCustomer] = useState(false)
  const [draft, setDraft] = useState<Order | null>(null)
  const [done, setDone] = useState<Order | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const branch = locations?.find((l) => String(l.id) === branchId)
  const warehouse = locations?.find((l) => l.code === 'PAW') ?? locations?.find((l) => l.can_release)
  const sellingBranches = locations?.filter((l) => l.can_sell && !l.can_release)

  // Re-issue a voided sale (P-45): pre-fill from it and link it with `replaces`.
  const original = useApi<Order>(replacesId ? `/orders/${replacesId}/` : null)
  useEffect(() => {
    const o = original.data
    if (!o?.lines) return
    setBranchId(String(o.branch))
    setChannel(o.channel)
    setReceiptType(o.receipt_type)
    setNotes(o.notes)
    api.get<Customer>(`/customers/${o.customer}/`).then(setCustomer).catch(() => {})
    Promise.all(o.lines.map((l) => api.get<Product>(`/products/${l.product}/`))).then((products) => {
      setLines(o.lines!.map((l, i) => ({
        key: `${l.id}`, product: { ...products[i], stock: {}, total_new: 0 }, qty: l.qty,
        source: l.source_location_code === o.branch_code ? 'branch' : 'warehouse',
        condition: l.condition, discount: l.discount === '0.00' ? '' : l.discount,
      })))
    }).catch(() => {})
  }, [original.data])

  // An official-receipt sale is paid only into Organization accounts (D3).
  const usableAccounts = (accounts ?? []).filter((a) => a.is_active !== false && (receiptType !== 'official' || a.kind === 'organization'))
  const account = usableAccounts.find((a) => String(a.id) === pay.account)
  useEffect(() => {
    if (payOn && !account && usableAccounts.length) {
      const first = usableAccounts[0]
      setPay((p) => ({ ...p, account: String(first.id), method: first.method }))
    }
  }, [payOn, account, usableAccounts])

  const maxDiscountPct = Number(settings?.max_salesperson_discount_pct ?? 0)
  const priced = useMemo(() => lines.map((l) => {
    const { price, wholesale } = priceFor(l.product, customer?.type)
    const gross = toCents(price) * l.qty
    const discount = toCents(l.discount)
    const overLimit = discount > 0 && !can('approve_discounts') && (discount / gross) * 100 > maxDiscountPct
    return { ...l, price, wholesale, gross, discountCents: discount, total: gross - discount, overLimit }
  }), [lines, customer?.type, can, maxDiscountPct])

  const subtotal = priced.reduce((s, l) => s + l.gross, 0)
  const discounts = priced.reduce((s, l) => s + l.discountCents, 0)
  const total = subtotal - discounts
  const paidNow = payOn ? toCents(pay.amount) : 0
  const remaining = Math.max(0, total - paidNow)
  const owesNow = toCents(customer?.outstanding)
  const owedAfter = owesNow + remaining
  const limit = customer?.credit_limit ? toCents(customer.credit_limit) : null

  const creditProblem = (() => {
    if (!customer || remaining <= 0 || can('approve_credit')) return null
    if (!customer.credit_allowed) return `${customer.name} does not buy on credit: ${money(fromCents(remaining))} would be unpaid. Take the payment first, or ask the accountant to approve.`
    if (limit !== null && owedAfter > limit) return `${customer.name} would owe ${money(fromCents(owedAfter))}, above their limit of ${money(fromCents(limit))}. Ask the accountant to approve.`
    return null
  })()

  const lineProblems = priced.flatMap((l) => {
    const out: string[] = []
    if (l.source === 'branch' && branch) {
      const cell = l.product.stock[branch.code]
      const free = !cell ? undefined : l.condition === 'new' ? cell.available : l.condition === 'display' ? cell.display : cell.damaged
      if (free !== undefined && l.qty > free) out.push(`Only ${free} ${l.product.code}${l.condition !== 'new' ? ` (${l.condition})` : ''} available at ${branch.code}.`)
    }
    if (l.source === 'warehouse' && warehouse) {
      const free = l.product.stock[warehouse.code]?.available
      if (free !== undefined && l.qty > free) out.push(`Only ${free} ${l.product.code} available at ${warehouse.code}.`)
    }
    if (l.discountCents > l.gross) out.push(`The discount on ${l.product.code} is more than the line.`)
    return out
  })

  const payProblem = (() => {
    if (!payOn) return null
    if (!account) return 'Choose the account the money went to.'
    if (paidNow <= 0) return 'Enter the amount paid.'
    if (paidNow > total) return 'The payment is more than the sale total.'
    if (account.kind === 'organization' && receiptType === 'official' && !pay.receipt.trim()) return 'The receipt number is required for an official-receipt sale.'
    return null
  })()

  const add = (product: PickedProduct) => {
    setLines((ls) => {
      const existing = ls.find((l) => l.product.id === product.id && l.condition === 'new')
      if (existing) return ls.map((l) => (l === existing ? { ...l, qty: l.qty + 1 } : l))
      const hereFree = branch ? product.stock[branch.code]?.available ?? 0 : 0
      return [...ls, { key: `${product.id}-${Date.now()}`, product, qty: 1, source: hereFree > 0 || !warehouse ? 'branch' : 'warehouse', condition: 'new', discount: '' }]
    })
  }
  const update = (key: string, patch: Partial<SaleLine>) => setLines((ls) => ls.map((l) => (l.key === key ? { ...l, ...patch } : l)))

  const orderBody = () => ({
    customer: customer!.id,
    ...(is('accountant', 'admin') && branchId ? { branch: Number(branchId) } : {}),
    channel, receipt_type: receiptType, notes,
    lines: priced.map((l) => ({
      product: l.product.id, qty: l.qty, condition: l.condition, discount: l.discount || '0',
      source_location: l.source === 'branch' ? Number(branchId) : warehouse?.id,
    })),
    ...(replacesId ? { replaces: Number(replacesId) } : {}),
  })

  /** Create (or update the draft), then confirm unless `confirm` is false. */
  const submit = async (confirm: boolean) => {
    if (!customer || !lines.length) return
    setBusy(true)
    setError(null)
    try {
      let order = draft
      if (!order) {
        const body: Record<string, unknown> = orderBody()
        if (payOn && account) {
          body.payment = {
            account: account.id, amount: fromCents(paidNow), method: pay.method,
            ...(account.kind === 'organization' && pay.receipt.trim() ? { receipt_number: pay.receipt.trim() } : {}),
          }
        }
        order = await api.post<Order>('/orders/', body)
        setDraft(order)
      } else {
        const { lines: newLines, notes: newNotes } = orderBody()
        order = await api.patch<Order>(`/orders/${order.id}/`, { lines: newLines, notes: newNotes })
      }
      if (confirm) order = await api.post<Order>(`/orders/${order.id}/confirm/`)
      await queryClient.invalidateQueries()
      setDone(order)
    } catch (e) {
      setError(errorMessage(e))
      if (e instanceof ApiError && e.status >= 500) setDraft(null)
    } finally {
      setBusy(false)
    }
  }

  if (replacesId && original.isLoading) return <main className="page"><Loading /></main>
  if (done) return <SaleDone order={done} confirmed={done.fulfillment_status !== 'draft' && done.fulfillment_status !== 'pending'} />

  const unitsCount = priced.reduce((s, l) => s + l.qty, 0)
  const canSubmit = Boolean(customer && lines.length && branchId) && !lineProblems.length && !payProblem && !priced.some((l) => l.overLimit)

  return (
    <main className="page">
      <PageHeader title={replacesId ? `Re-issue ${original.data?.number ?? ''}` : 'New sale'}
        sub={`${branch?.name ?? 'Choose a branch'} · ${formatBoth(isoDate(todayAddis()))}`}
        actions={<Seg labelText="Channel" value={channel} onChange={setChannel} options={[['walk_in', 'Walk-in'], ['phone', 'Phone order']]} />} />
      {replacesId && <Banner kind="info">This sale replaces the voided <span className="mono">{original.data?.number}</span>. Check the lines, then confirm.</Banner>}
      {draft && <Banner kind="warn"><span>Saved as draft <span className="mono">{draft.number}</span>{payOn ? ' with its payment' : ''}. Fix the problem and confirm again, or <Link to={`/sales/${draft.id}`}>open the draft</Link>.</span></Banner>}
      <div className="with-aside">
        <div className="stack" style={{ gap: 20, minWidth: 0 }}>
          {is('accountant', 'admin') && (
            <Card>
              <Field label="Branch" style={{ maxWidth: 320 }}>{(id) => (
                <select id={id} className="inp" value={branchId} disabled={Boolean(draft)} onChange={(e) => setBranchId(e.target.value)}>
                  <option value="">Choose…</option>
                  {sellingBranches?.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
                </select>
              )}</Field>
            </Card>
          )}
          <Card title="1 · Customer" actions={!customer && (
            <div className="row">
              <button type="button" className="btn btn-sec" disabled={!walkIn} onClick={() => walkIn && setCustomer(walkIn)}>Walk-in customer</button>
              <button type="button" className="btn btn-sec" onClick={() => setNewCustomer(true)}>+ New customer</button>
            </div>
          )}>
            {customer ? (
              <div className="row" style={{ gap: 24, alignItems: 'flex-start' }}>
                <div className="stack grow" style={{ gap: 2 }}>
                  <Link to={`/customers/${customer.id}`} style={{ fontWeight: 600, fontSize: 16 }}>{customer.name}</Link>
                  <span className="sub">{[label(customer.type), customer.shop_name, customer.city, customer.phone].filter(Boolean).join(' · ')}</span>
                </div>
                <div className="stack" style={{ gap: 2 }}><span className="sub">Credit</span><span style={{ fontWeight: 600 }}>{customer.credit_allowed ? 'Allowed' : 'Not allowed'}</span></div>
                <div className="stack" style={{ gap: 2 }}><span className="sub">Owes now</span><span className="num" style={{ fontWeight: 600 }}>{money(customer.outstanding)}</span></div>
                <div className="stack" style={{ gap: 2 }}><span className="sub">Limit</span><span className="num" style={{ fontWeight: 600 }}>{customer.credit_allowed ? (customer.credit_limit ? money(customer.credit_limit) : 'No limit') : '—'}</span></div>
                {!draft && <button type="button" className="btn btn-sec" onClick={() => setCustomer(null)}>Change</button>}
              </div>
            ) : (
              <div style={{ maxWidth: 520 }}><CustomerPicker onPick={setCustomer} onNew={() => setNewCustomer(true)} autoFocus /></div>
            )}
          </Card>

          <Card title="2 · Products">
            <div style={{ maxWidth: 560 }}>
              <ProductPicker onPick={add} customerType={customer?.type} stockAt={[branch?.code, warehouse?.code].filter(Boolean) as string[]} placeholder="Add product — type code or name" />
            </div>
            {lines.length > 0 && (
              <div style={{ overflowX: 'auto' }}>
                <table className="tbl tbl-cmp">
                  <thead><tr><th>Product</th><th className="r">Price</th><th>Here / {warehouse?.code}</th><th>Qty</th><th>Source</th><th>Condition</th><th className="r">Discount</th><th className="r">Line total</th><th><span className="sr-only">Remove</span></th></tr></thead>
                  <tbody>
                    {priced.map((l) => {
                      const here = branch ? l.product.stock[branch.code]?.available : undefined
                      const paw = warehouse ? l.product.stock[warehouse.code]?.available : undefined
                      return (
                        <tr key={l.key}>
                          <td><span className="mono" style={{ fontWeight: 600 }}>{l.product.code}</span> <span className="sub">{l.product.name}</span></td>
                          <td className="r"><div>{money(l.price)}</div>{l.wholesale && <span className="tag t-blue">Wholesale</span>}</td>
                          <td>{here ?? '—'} <span className="sub">/ {paw ?? '—'}</span></td>
                          <td><QtyStepper value={l.qty} min={1} onChange={(qty) => update(l.key, { qty })} label={l.product.code} /></td>
                          <td>
                            <select className="inp" style={{ height: 36, width: 150 }} aria-label="Source" value={l.source}
                              onChange={(e) => update(l.key, { source: e.target.value as SaleLine['source'], condition: e.target.value === 'warehouse' ? 'new' : l.condition })}>
                              <option value="branch">From this branch</option>
                              {warehouse && <option value="warehouse">From {warehouse.name.split(' ')[0]}</option>}
                            </select>
                          </td>
                          <td>
                            <select className="inp" style={{ height: 36, width: 110 }} aria-label="Condition" value={l.condition} onChange={(e) => update(l.key, { condition: e.target.value as SaleLine['condition'] })}>
                              <option value="new">New</option>
                              {l.source === 'branch' && <><option value="display">Display</option><option value="damaged">Damaged</option></>}
                            </select>
                          </td>
                          <td className="r" style={{ width: 150 }}>
                            <MoneyInput value={l.discount} onChange={(v) => update(l.key, { discount: v })} placeholder="0.00" />
                            {l.overLimit && <div className="fld-err" style={{ whiteSpace: 'normal' }}>Above the {maxDiscountPct}% limit — needs discount approval</div>}
                          </td>
                          <td className="r" style={{ fontWeight: 600 }}>{money(fromCents(l.total))}</td>
                          <td><button type="button" className="x-btn" aria-label={`Remove ${l.product.code}`} onClick={() => setLines(lines.filter((x) => x.key !== l.key))}>×</button></td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
            <span className="sub" style={{ fontSize: 13 }}>Prices come from the product — resellers get the wholesale price. Display and damaged pieces can only come from this branch. Lines from {warehouse?.name ?? 'the warehouse'} become a stock request when you confirm.</span>
            {lineProblems.map((p) => <ErrorBanner key={p} text={p} />)}
          </Card>

          {!draft && (
            <Card title={<>3 · Pay now <span className="muted" style={{ fontWeight: 400 }}>(optional)</span></>}
              actions={<label className="check"><input type="checkbox" checked={payOn} onChange={(e) => setPayOn(e.target.checked)} />Customer pays now</label>}>
              {payOn && (usableAccounts.length === 0 ? <Banner kind="warn">No payment account you may use{receiptType === 'official' ? ' for an official-receipt sale (Organization only)' : ''}. Ask the admin.</Banner> : (
                <>
                  <div className="stack" role="radiogroup" aria-label="Account" style={{ gap: 8 }}>
                    {usableAccounts.map((a) => (
                      <label key={a.id} className="check" style={{ padding: '10px 12px', border: `1px solid ${String(a.id) === pay.account ? 'var(--primary)' : 'var(--line)'}`, borderRadius: 8 }}>
                        <input type="radio" name="acc" checked={String(a.id) === pay.account} onChange={() => setPay({ ...pay, account: String(a.id), method: a.method, receipt: a.kind === 'personal' ? '' : pay.receipt })} />
                        <KindBadge kind={a.kind} /><span>{a.name}</span>
                      </label>
                    ))}
                  </div>
                  {receiptType === 'official' && <span className="sub">Official-receipt sale: only Organization accounts are offered.</span>}
                  <div className="form-grid">
                    <Field label="Amount">{(id) => <MoneyInput id={id} value={pay.amount} onChange={(v) => setPay({ ...pay, amount: v })} />}</Field>
                    <Field label="Method">{(id) => (
                      <select id={id} className="inp" value={pay.method} onChange={(e) => setPay({ ...pay, method: e.target.value })}>
                        <option value="bank">Bank transfer</option><option value="cash">Cash</option><option value="mobile_money">Mobile money</option>
                      </select>
                    )}</Field>
                    {account?.kind === 'organization' && (
                      <Field label="Receipt number" hint={receiptType === 'official' ? 'Required for Organization on an official sale' : 'Optional'}>{(id) => <input id={id} className="inp mono" value={pay.receipt} onChange={(e) => setPay({ ...pay, receipt: e.target.value })} />}</Field>
                    )}
                  </div>
                  <button type="button" className="btn btn-q" style={{ alignSelf: 'flex-start' }} onClick={() => setPay({ ...pay, amount: fromCents(total) })}>Pay the full {money(fromCents(total))}</button>
                  {payProblem && pay.amount && <span className="fld-err">{payProblem}</span>}
                </>
              ))}
            </Card>
          )}
          <Field label="Notes (optional)">{(id) => <input id={id} className="inp" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Shown on the sale and the stock request" />}</Field>
        </div>

        <aside className="stack" style={{ gap: 20 }}>
          <Card title="Receipt type">
            <div className="stack" role="radiogroup" aria-label="Receipt type" style={{ gap: 8 }}>
              {(['official', 'none'] as const).map((rt) => (
                <label key={rt} className="check"><input type="radio" name="rt" disabled={Boolean(draft)} checked={receiptType === rt} onChange={() => setReceiptType(rt)} />{label(rt)}</label>
              ))}
            </div>
          </Card>
          <Card title="Summary">
            <div className="spread"><span className="muted">Subtotal · {lines.length} lines, {unitsCount} units</span><span className="num">{money(fromCents(subtotal))}</span></div>
            {discounts > 0 && <div className="spread"><span className="muted">Discounts</span><span className="num">−{money(fromCents(discounts))}</span></div>}
            <div className="spread" style={{ fontSize: 18, fontWeight: 700 }}><span>Total</span><span className="num">{money(fromCents(total))} <span className="sub">ETB</span></span></div>
            <div className="spread"><span className="muted">Paid now</span><span className="num">{money(fromCents(paidNow))}</span></div>
            <div className="spread" style={{ fontWeight: 600 }}><span>Remaining (credit)</span><span className="num">{money(fromCents(remaining))}</span></div>
            {customer && remaining > 0 && customer.credit_allowed && limit !== null && !creditProblem && owedAfter > limit * 0.85 && (
              <Banner kind="warn"><span><strong>Close to the credit limit.</strong> {customer.name} would owe {money(fromCents(owedAfter))} of {money(fromCents(limit))} ETB.</span></Banner>
            )}
            {creditProblem && <Banner kind="err">{creditProblem}</Banner>}
            {error && <ErrorBanner text={error} />}
            <button type="button" className="btn btn-pri btn-lg" disabled={!canSubmit || busy || Boolean(creditProblem)} onClick={() => submit(true)}>
              {busy ? 'Saving…' : channel === 'phone' ? 'Confirm order' : 'Confirm sale'}
            </button>
            <button type="button" className="btn btn-sec" disabled={!canSubmit || busy} onClick={() => submit(false)}>
              {channel === 'phone' ? 'Save as pending' : 'Save as draft'}
            </button>
          </Card>
          <Card>
            <span className="lbl">After you confirm</span>
            <span className="sub" style={{ fontSize: 13 }}>You get the SO number in large type, a delivery note for the goods taken now{priced.some((l) => l.source === 'warehouse') ? `, and a stock request for ${priced.filter((l) => l.source === 'warehouse').map((l) => `${l.qty} × ${l.product.code}`).join(', ')} from ${warehouse?.code}` : ''}.</span>
          </Card>
        </aside>
      </div>
      {newCustomer && (
        <Dialog title="New customer" panel onClose={() => setNewCustomer(false)}>
          <CustomerEditor onSaved={(c) => { setCustomer(c); setNewCustomer(false) }} onCancel={() => setNewCustomer(false)} />
        </Dialog>
      )}
    </main>
  )
}

function SaleDone({ order, confirmed }: { order: Order; confirmed: boolean }) {
  return (
    <main className="page" style={{ maxWidth: 820 }}>
      <Card>
        <span className="lbl">{confirmed ? (order.channel === 'phone' ? 'Order confirmed' : 'Sale confirmed') : order.fulfillment_status === 'pending' ? 'Saved as pending' : 'Saved as draft'}</span>
        <span className="big-number" style={{ fontSize: 40 }}>{order.number}</span>
        <div className="row" style={{ gap: 24 }}>
          <span>{order.customer_name}</span>
          <span className="num">Total <strong>{money(order.total)}</strong></span>
          <span className="num">Paid <strong>{money(order.paid)}</strong></span>
          <span className="num">Remaining <strong>{money(order.remaining)}</strong></span>
        </div>
        {order.delivery_notes && order.delivery_notes.length > 0 && (
          <div className="stack" style={{ gap: 6 }}>
            <span className="lbl">Handed over now</span>
            {order.delivery_notes.map((dn) => (
              <div key={dn.id} className="row">
                <span className="mono">{dn.number}</span>
                <span className="muted">{dn.lines.map((l) => `${l.qty} × ${l.product_code}`).join(', ')}</span>
                <Link className="btn btn-sec btn-sm" to={`/delivery-notes/${dn.id}`} target="_blank">Print delivery note</Link>
              </div>
            ))}
          </div>
        )}
        {order.stock_requests && order.stock_requests.length > 0 && (
          <div className="stack" style={{ gap: 6 }}>
            <span className="lbl">What happens next</span>
            {order.stock_requests.map((sr) => (
              <span key={sr.id}>Requested from the warehouse — <Link className="mono" to={`/stock-requests/${sr.id}`}>{sr.number}</Link>. The storekeeper releases it; the goods are held here for the customer.</span>
            ))}
          </div>
        )}
        <div className="row">
          <Link className="btn btn-pri" to={`/sales/${order.id}`}>Open the sale</Link>
          {Number(order.remaining) > 0 && confirmed && <Link className="btn btn-sec" to={`/payments/new?order=${order.id}`}>Record payment</Link>}
          <a className="btn btn-sec" href="/sales/new">New sale</a>
        </div>
      </Card>
    </main>
  )
}
