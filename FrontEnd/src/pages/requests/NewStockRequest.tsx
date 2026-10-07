import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import { useAction, useRealLocations } from '../../api/hooks'
import type { Customer, StockRequest } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { ConfirmDialog } from '../../components/Dialog'
import { LinesEditor, linesSummary } from '../../components/LinesEditor'
import type { EditorLine } from '../../components/LinesEditor'
import { CustomerPicker } from '../../components/pickers'
import { Card, Field, PageHeader } from '../../components/ui'

// P-31 New stock request — restocking the branch. (Requests for a customer's sale are made
// automatically by New sale.) Quantities can't exceed what is free at the source.
export default function NewStockRequest() {
  const { user, is } = useAuth()
  const { data: locations } = useRealLocations()
  const shops = locations?.filter((l) => l.can_sell && !l.can_release)
  const sources = locations?.filter((l) => l.can_release)
  const [branch, setBranch] = useState(String(user?.home_location ?? ''))
  const [source, setSource] = useState('')
  const [customer, setCustomer] = useState<Customer | null>(null)
  const [reference, setReference] = useState('')
  const [notes, setNotes] = useState('')
  const [lines, setLines] = useState<EditorLine[]>([])
  const [confirm, setConfirm] = useState(false)
  const [done, setDone] = useState<StockRequest | null>(null)
  const sourceLoc = sources?.find((l) => String(l.id) === source) ?? sources?.find((l) => l.code === 'PAW') ?? sources?.[0]
  const branchLoc = locations?.find((l) => String(l.id) === branch)

  const save = useAction(() => api.post<StockRequest>('/stock-requests/', {
    ...(is('admin') && branch ? { requesting_location: Number(branch) } : {}),
    source_location: sourceLoc?.id,
    customer: customer?.id ?? null, reference, notes,
    lines: lines.map((l) => ({ product: l.product.id, qty: l.qty })),
  }), { onSuccess: (r) => setDone(r as StockRequest), toastErrors: false })

  if (done) {
    return (
      <main className="page" style={{ maxWidth: 760 }}>
        <Card>
          <span className="lbl">Request sent to {done.source_location_code}</span>
          <span className="big-number">{done.number}</span>
          <span>{done.lines.map((l) => `${l.qty_requested} × ${l.product_code}`).join(', ')} — the storekeeper is told in Telegram.</span>
          <div className="row">
            <Link className="btn btn-pri" to={`/stock-requests/${done.id}`}>Open the request</Link>
            <button type="button" className="btn btn-sec" onClick={() => { setDone(null); setLines([]); setCustomer(null); setReference(''); setNotes('') }}>New request</button>
          </div>
        </Card>
      </main>
    )
  }

  return (
    <main className="page" style={{ maxWidth: 1100 }}>
      <Link to="/stock-requests" style={{ fontSize: 14 }}>← Stock requests</Link>
      <PageHeader title="New stock request" sub="Restock the branch from the warehouse" />
      <Card>
        <div className="form-grid">
          <Field label="For branch">{(id) => (
            <select id={id} className="inp" value={branch} disabled={!is('admin')} onChange={(e) => setBranch(e.target.value)}>
              <option value="">Choose…</option>{shops?.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          )}</Field>
          <Field label="From">{(id) => (
            <select id={id} className="inp" value={String(sourceLoc?.id ?? '')} onChange={(e) => setSource(e.target.value)}>
              {sources?.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          )}</Field>
          <Field label="Customer (optional)" hint="Needed if the customer collects at the warehouse">{(id) => customer
            ? <div className="row" style={{ height: 42 }}><strong>{customer.name}</strong><button type="button" className="btn btn-q btn-sm" onClick={() => setCustomer(null)}>Change</button></div>
            : <CustomerPicker id={id} onPick={setCustomer} />}</Field>
          <Field label="Reference">{(id) => <input id={id} className="inp" value={reference} onChange={(e) => setReference(e.target.value)} placeholder="e.g. Weekly restock" maxLength={200} />}</Field>
        </div>
        <LinesEditor lines={lines} onChange={setLines} stockAt={sourceLoc ? [sourceLoc.code] : []}
          maxFor={(l) => (sourceLoc ? l.product.stock[sourceLoc.code]?.available ?? 0 : undefined)}
          extra={(l) => sourceLoc && <span className="sub">{l.product.stock[sourceLoc.code]?.available ?? 0} free at {sourceLoc.code}</span>} />
        <Field label="Notes">{(id) => <textarea id={id} className="inp" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />}</Field>
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          <Link className="btn btn-sec" to="/stock-requests">Cancel</Link>
          <button type="button" className="btn btn-pri" disabled={!lines.length || !branch} onClick={() => setConfirm(true)}>Send request</button>
        </div>
      </Card>
      {confirm && (
        <ConfirmDialog title="Send stock request"
          message={<>Request <strong>{linesSummary(lines)}</strong> from {sourceLoc?.name} for {branchLoc?.name}{customer ? ` (customer ${customer.name})` : ''}? The stock is reserved at {sourceLoc?.code} now.</>}
          confirmLabel="Send request" onConfirm={() => save.mutateAsync(undefined)} onClose={() => setConfirm(false)} />
      )}
    </main>
  )
}
