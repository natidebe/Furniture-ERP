import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ApiError, api } from '../../api/client'
import { useAction, useApi, usePaymentAccounts } from '../../api/hooks'
import type { Customer, Order, Paginated, Payment } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { ConfirmDialog } from '../../components/Dialog'
import { EthDatePicker } from '../../components/EthDatePicker'
import { MoneyInput } from '../../components/inputs'
import { CustomerPicker } from '../../components/pickers'
import { Banner, Card, DocLink, Empty, ErrorBanner, Field, KindBadge, PageHeader, StatusChip } from '../../components/ui'
import { fromCents, money, toCents } from '../../lib/format'
import { label } from '../../lib/labels'

interface Alloc { order: Order; amount: string; byLine: boolean; lines: Record<number, string> }

// P-50 Record payment — from a sale, a customer, or the menu. Money can go to specific sales
// and lines; what is not allocated stays the customer's advance until the accountant allocates
// it (Q20). Salespeople's payments start Unverified.
export default function RecordPayment() {
  const { is } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const orderParam = params.get('order')
  const customerParam = params.get('customer')
  const { data: accounts } = usePaymentAccounts()
  const [customer, setCustomer] = useState<Customer | null>(null)
  const [accountId, setAccountId] = useState('')
  const [amount, setAmount] = useState('')
  const [method, setMethod] = useState('cash')
  const [receipt, setReceipt] = useState('')
  const [paidOn, setPaidOn] = useState('')
  const [note, setNote] = useState('')
  const [allocs, setAllocs] = useState<Record<number, Alloc>>({})
  const [confirm, setConfirm] = useState(false)
  const [error, setError] = useState<unknown>(null)

  const preOrder = useApi<Order>(orderParam ? `/orders/${orderParam}/` : null)
  useEffect(() => {
    const id = preOrder.data?.customer ?? (customerParam ? Number(customerParam) : null)
    if (id && !customer) api.get<Customer>(`/customers/${id}/`).then(setCustomer).catch(() => {})
  }, [preOrder.data, customerParam, customer])
  useEffect(() => {
    const o = preOrder.data
    if (o && !allocs[o.id]) {
      setAllocs((a) => ({ ...a, [o.id]: { order: o, amount: o.remaining, byLine: false, lines: {} } }))
      setAmount((x) => x || o.remaining)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preOrder.data])

  const owing = useApi<Paginated<Order>>(customer ? '/orders/' : null, { customer: customer?.id, owing: 'true', ordering: 'confirmed_at', page_size: 50 })
  const activeAccounts = (accounts ?? []).filter((a) => a.is_active !== false)
  const account = activeAccounts.find((a) => String(a.id) === accountId)
  useEffect(() => {
    if (!accountId && activeAccounts.length === 1) { setAccountId(String(activeAccounts[0].id)); setMethod(activeAccounts[0].method) }
  }, [accountId, activeAccounts])

  const allocList = Object.values(allocs).filter((a) => a.byLine ? Object.values(a.lines).some((v) => toCents(v) > 0) : toCents(a.amount) > 0)
  const allocCents = (a: Alloc) => (a.byLine ? Object.values(a.lines).reduce((s, v) => s + toCents(v), 0) : toCents(a.amount))
  const allocated = allocList.reduce((s, a) => s + allocCents(a), 0)
  const total = toCents(amount)
  const advance = Math.max(0, total - allocated)
  const officialAllocated = allocList.some((a) => a.order.receipt_type === 'official')

  const problems: string[] = []
  if (allocated > total) problems.push('More is allocated than the payment.')
  for (const a of allocList) {
    if (!a.byLine && allocCents(a) > toCents(a.order.remaining)) problems.push(`${a.order.number}: more than its remaining ${money(a.order.remaining)}.`)
    if (a.byLine) for (const l of a.order.lines ?? []) {
      if (toCents(a.lines[l.id]) > toCents(l.remaining)) problems.push(`${a.order.number} ${l.product_code}: more than the line's remaining ${money(l.remaining)}.`)
    }
  }
  if (account?.kind === 'personal' && officialAllocated) problems.push('An official-receipt sale is paid only into an Organization account.')
  if (account?.kind === 'organization' && officialAllocated && !receipt.trim()) problems.push('The receipt number is required for an official-receipt sale.')

  const save = useAction(() => api.post<Payment>('/payments/', {
    customer: customer!.id, account: account!.id, amount, method, note,
    ...(account?.kind === 'organization' && receipt.trim() ? { receipt_number: receipt.trim() } : {}),
    ...(paidOn ? { paid_at: `${paidOn}T12:00:00+03:00` } : {}),
    allocations: allocList.flatMap((a) => (a.byLine
      ? (a.order.lines ?? []).filter((l) => toCents(a.lines[l.id]) > 0).map((l) => ({ order: a.order.id, line: l.id, amount: a.lines[l.id] }))
      : [{ order: a.order.id, amount: a.amount }])),
  }), { success: (p) => `${(p as Payment).number} recorded${is('salesperson') ? ' — waiting for the accountant to verify' : ''}.`, onSuccess: (p) => navigate(`/payments/${(p as Payment).id}`), toastErrors: false })

  const toggleOrder = async (o: Order, on: boolean) => {
    if (!on) { const next = { ...allocs }; delete next[o.id]; setAllocs(next); return }
    setAllocs({ ...allocs, [o.id]: { order: o, amount: o.remaining, byLine: false, lines: {} } })
  }
  const splitByLine = async (a: Alloc) => {
    const full = a.order.lines ? a.order : await api.get<Order>(`/orders/${a.order.id}/`)
    setAllocs({ ...allocs, [a.order.id]: { ...a, order: full, byLine: true } })
  }
  const fields = error instanceof ApiError ? error.fields : {}

  return (
    <main className="page" style={{ maxWidth: 1100 }}>
      <PageHeader title="Record payment" sub="Money received from a customer" />
      <div className="with-aside">
        <div className="stack" style={{ gap: 20, minWidth: 0 }}>
          <Card title="Customer">
            {customer ? (
              <div className="row">
                <Link to={`/customers/${customer.id}`} style={{ fontWeight: 600, fontSize: 16 }}>{customer.name}</Link>
                <span className="sub">{label(customer.type)} · owes {money(customer.outstanding)}</span>
                {!orderParam && <button type="button" className="btn btn-q btn-sm" onClick={() => { setCustomer(null); setAllocs({}) }}>Change</button>}
              </div>
            ) : <div style={{ maxWidth: 520 }}><CustomerPicker onPick={setCustomer} autoFocus /></div>}
          </Card>
          <Card title="Payment">
            {activeAccounts.length === 0 && <Banner kind="warn">No payment account you may use. Ask the admin.</Banner>}
            <div className="stack" role="radiogroup" aria-label="Account" style={{ gap: 8 }}>
              {activeAccounts.map((a) => (
                <label key={a.id} className="check" style={{ padding: '10px 12px', border: `1px solid ${String(a.id) === accountId ? 'var(--primary)' : 'var(--line)'}`, borderRadius: 8 }}>
                  <input type="radio" name="acc" checked={String(a.id) === accountId} onChange={() => { setAccountId(String(a.id)); setMethod(a.method); if (a.kind === 'personal') setReceipt('') }} />
                  <KindBadge kind={a.kind} /><span>{a.name}</span><span className="sub">{label(a.method)}</span>
                </label>
              ))}
            </div>
            <div className="form-grid">
              <Field label="Amount" error={fields.amount}>{(id) => <MoneyInput id={id} value={amount} onChange={setAmount} />}</Field>
              <Field label="Method" error={fields.method}>{(id) => (
                <select id={id} className="inp" value={method} onChange={(e) => setMethod(e.target.value)}>
                  <option value="bank">Bank transfer</option><option value="cash">Cash</option><option value="mobile_money">Mobile money</option>
                </select>
              )}</Field>
              {account?.kind !== 'personal' && (
                <Field label="Receipt number" hint={officialAllocated ? 'Required: official-receipt sale' : 'Organization only; one per payment'} error={fields.receipt_number}>{(id) => <input id={id} className="inp mono" value={receipt} onChange={(e) => setReceipt(e.target.value)} />}</Field>
              )}
              <Field label="Date paid" hint="Empty: now">{(id) => <EthDatePicker id={id} value={paidOn} onChange={setPaidOn} placeholder="Today" />}</Field>
            </div>
            {account?.kind === 'personal' && <span className="sub">Personal account: no receipt number.</span>}
            <Field label="Note">{(id) => <input id={id} className="inp" value={note} onChange={(e) => setNote(e.target.value)} maxLength={255} />}</Field>
          </Card>
          {customer && (
            <Card title="Pay for">
              {owing.data?.results.length === 0 && !Object.keys(allocs).length ? <Empty title="No sales waiting for payment" hint="The whole payment stays the customer's advance." /> : (
                <div className="stack" style={{ gap: 10 }}>
                  {[...new Map([...(owing.data?.results ?? []), ...Object.values(allocs).map((a) => a.order)].map((o) => [o.id, o])).values()].map((o) => {
                    const a = allocs[o.id]
                    return (
                      <div key={o.id} className="card" style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
                        <div className="row">
                          <label className="check"><input type="checkbox" checked={Boolean(a)} onChange={(e) => toggleOrder(o, e.target.checked)} /><DocLink number={o.number} to={`/sales/${o.id}`} /></label>
                          <span className="sub">{o.created_at_ec.split(' (')[0]} · {o.receipt_type === 'official' ? 'Official receipt' : 'No receipt'}</span>
                          <StatusChip kind="orderPayment" value={o.payment_status} />
                          <span className="grow r num">remaining <strong>{money(o.remaining)}</strong></span>
                          {a && !a.byLine && <div style={{ width: 170 }}><MoneyInput value={a.amount} onChange={(v) => setAllocs({ ...allocs, [o.id]: { ...a, amount: v } })} /></div>}
                        </div>
                        {a && !a.byLine && <button type="button" className="btn btn-q btn-sm" style={{ alignSelf: 'flex-start' }} onClick={() => splitByLine(a)}>Pay for specific lines…</button>}
                        {a?.byLine && (
                          <table className="tbl tbl-cmp">
                            <tbody>
                              {(a.order.lines ?? []).map((l) => (
                                <tr key={l.id}>
                                  <td>For: {l.qty} × <span className="mono">{l.product_code}</span> <span className="sub">{l.product_name}</span></td>
                                  <td className="r sub">remaining {money(l.remaining)}</td>
                                  <td style={{ width: 170 }}><MoneyInput value={a.lines[l.id] ?? ''} onChange={(v) => setAllocs({ ...allocs, [o.id]: { ...a, lines: { ...a.lines, [l.id]: v } } })} /></td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </Card>
          )}
        </div>
        <aside className="stack" style={{ gap: 20 }}>
          <Card title="Summary">
            <div className="spread"><span className="muted">Payment</span><span className="num" style={{ fontWeight: 700 }}>{money(amount || 0)}</span></div>
            <div className="spread"><span className="muted">To sales</span><span className="num">{money(fromCents(allocated))}</span></div>
            <div className="spread"><span className="muted">Customer's advance</span><span className="num">{money(fromCents(advance))}</span></div>
            {advance > 0 && <span className="sub">Unallocated money stays the customer's advance until the accountant allocates it.</span>}
            {is('salesperson') && <span className="sub">Your payments start Unverified until the accountant checks them.</span>}
            {problems.map((p) => <ErrorBanner key={p} text={p} />)}
            {Boolean(error) && <ErrorBanner error={error} />}
            <button type="button" className="btn btn-pri btn-lg" disabled={!customer || !account || total <= 0 || problems.length > 0} onClick={() => setConfirm(true)}>Record payment</button>
          </Card>
        </aside>
      </div>
      {confirm && account && customer && (
        <ConfirmDialog title="Record payment"
          message={<>Record <strong>{money(amount)} ETB</strong> from {customer.name} into <KindBadge kind={account.kind} /> {account.name}{receipt && `, receipt ${receipt}`}?{allocList.length > 0 && <> For {allocList.map((a) => a.order.number).join(', ')}.</>}{advance > 0 && <> {money(fromCents(advance))} stays as advance.</>}</>}
          confirmLabel="Record" onConfirm={() => save.mutateAsync(undefined).catch((e) => { setError(e); throw e })} onClose={() => setConfirm(false)} />
      )}
    </main>
  )
}
