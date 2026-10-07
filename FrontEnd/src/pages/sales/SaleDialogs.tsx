import { useState } from 'react'
import { api } from '../../api/client'
import { useAction, useRealLocations } from '../../api/hooks'
import type { Order, OrderLine } from '../../api/types'
import { Dialog } from '../../components/Dialog'
import { MoneyInput, QtyStepper } from '../../components/inputs'
import { Banner, CondTag, ErrorBanner, Field } from '../../components/ui'
import { money } from '../../lib/format'

/** A dialog listing lines with a quantity each; posts [{line_id, qty}] for the non-zero ones. */
function LinesDialog({ title, intro, lines, maxFor, initial, confirmLabel, onSubmit, onClose, extra }: {
  title: string
  intro: React.ReactNode
  lines: OrderLine[]
  maxFor: (l: OrderLine) => number
  initial?: (l: OrderLine) => number
  confirmLabel: string
  onSubmit: (lines: { line_id: number; qty: number }[]) => Promise<unknown>
  onClose: () => void
  extra?: React.ReactNode
}) {
  const usable = lines.filter((l) => maxFor(l) > 0)
  const [qty, setQty] = useState<Record<number, number>>(Object.fromEntries(usable.map((l) => [l.id, initial ? initial(l) : maxFor(l)])))
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const chosen = usable.filter((l) => (qty[l.id] ?? 0) > 0).map((l) => ({ line_id: l.id, qty: qty[l.id] }))
  const go = async () => {
    setBusy(true)
    setError(null)
    try { await onSubmit(chosen); onClose() } catch (e) { setError(e); setBusy(false) }
  }
  return (
    <Dialog title={title} onClose={onClose} wide footer={<>
      <button type="button" className="btn btn-sec" onClick={onClose}>Cancel</button>
      <button type="button" className="btn btn-pri" disabled={!chosen.length || busy} onClick={go}>{busy ? 'Working…' : confirmLabel}</button>
    </>}>
      <div>{intro}</div>
      {usable.length === 0 ? <Banner kind="info">No line has anything left for this.</Banner> : (
        <div className="tw">
          <table className="tbl">
            <thead><tr><th>Product</th><th>Condition</th><th>Quantity</th></tr></thead>
            <tbody>
              {usable.map((l) => (
                <tr key={l.id}>
                  <td><span className="mono" style={{ fontWeight: 600 }}>{l.product_code}</span> {l.product_name}</td>
                  <td><CondTag condition={l.condition} /></td>
                  <td><QtyStepper value={qty[l.id] ?? 0} max={maxFor(l)} onChange={(v) => setQty({ ...qty, [l.id]: v })} label={l.product_code} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {extra}
      {Boolean(error) && <ErrorBanner error={error} />}
    </Dialog>
  )
}

/** Hand over at the branch: held goods first, then free branch stock. */
export function HandOverDialog({ order, onClose }: { order: Order; onClose: () => void }) {
  const run = useAction((lines: { line_id: number; qty: number }[]) => api.post(`/orders/${order.id}/release-from-branch/`, { lines }), { success: 'Handed over — the delivery note is ready.', toastErrors: false })
  return (
    <LinesDialog title="Hand over at branch" confirmLabel="Hand over"
      intro={<>Give <strong>{order.customer_name}</strong> the goods now at {order.branch_code}. A delivery note is made for what you hand over.</>}
      lines={order.lines ?? []}
      maxFor={(l) => l.qty - l.qty_released - l.qty_returned}
      initial={(l) => (l.qty_awaiting > 0 ? l.qty_awaiting : 0)}
      onSubmit={(lines) => run.mutateAsync(lines)} onClose={onClose} />
  )
}

/** Ask the warehouse again for what a rejected or short request did not bring. */
export function RequestStockDialog({ order, onClose }: { order: Order; onClose: () => void }) {
  const run = useAction((lines: { line_id: number; qty: number }[]) => api.post(`/orders/${order.id}/request-stock/`, { lines }), { success: 'Stock requested from the warehouse.', toastErrors: false })
  return (
    <LinesDialog title="Request remaining stock" confirmLabel="Send request"
      intro="Request from the warehouse what is still missing for this sale (after a rejected or short request)."
      lines={order.lines ?? []}
      maxFor={(l) => l.qty - l.qty_released - l.qty_awaiting - l.qty_returned}
      initial={() => 0}
      onSubmit={(lines) => run.mutateAsync(lines)} onClose={onClose} />
  )
}

/** P-45 Return goods: each line back as new or damaged, into a location, with a reason. */
export function ReturnDialog({ order, onClose }: { order: Order; onClose: () => void }) {
  const { data: locations } = useRealLocations()
  const [location, setLocation] = useState(String(order.branch))
  const [reason, setReason] = useState('')
  const [conditions, setConditions] = useState<Record<number, 'new' | 'damaged'>>({})
  const run = useAction((lines: { line_id: number; qty: number }[]) => api.post(`/orders/${order.id}/return/`, {
    location: Number(location), reason,
    lines: lines.map((l) => ({ ...l, condition: conditions[l.line_id] ?? 'new' })),
  }), { success: 'Return recorded.', toastErrors: false })
  const lines = order.lines ?? []
  return (
    <LinesDialog title="Return goods" confirmLabel="Record return"
      intro={<>Goods come back into stock and the sale total drops. Money paid beyond the new total becomes {order.customer_name}'s credit.</>}
      lines={lines}
      maxFor={(l) => l.qty_released - l.qty_returned}
      initial={() => 0}
      onSubmit={(chosen) => {
        if (!reason.trim()) return Promise.reject(new Error('A reason is required.'))
        return run.mutateAsync(chosen)
      }}
      onClose={onClose}
      extra={<>
        <div className="form-grid">
          <Field label="Back into">{(id) => (
            <select id={id} className="inp" value={location} onChange={(e) => setLocation(e.target.value)}>
              {locations?.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          )}</Field>
          {lines.filter((l) => l.qty_released - l.qty_returned > 0).map((l) => (
            <Field key={l.id} label={`${l.product_code} comes back as`}>{(id) => (
              <select id={id} className="inp" value={conditions[l.id] ?? 'new'} onChange={(e) => setConditions({ ...conditions, [l.id]: e.target.value as 'new' | 'damaged' })}>
                <option value="new">New</option><option value="damaged">Damaged</option>
              </select>
            )}</Field>
          ))}
        </div>
        <Field label="Reason (required)">{(id) => <input id={id} className="inp" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Wrong colour, customer returned 2 chairs" />}</Field>
      </>} />
  )
}

/** Edit a draft or pending sale: quantities, discounts and notes (prices come from the product). */
export function EditDraftDialog({ order, onClose }: { order: Order; onClose: () => void }) {
  const [lines, setLines] = useState((order.lines ?? []).map((l) => ({ ...l, discountText: l.discount === '0.00' ? '' : l.discount })))
  const [notes, setNotes] = useState(order.notes)
  const [error, setError] = useState<unknown>(null)
  const { data: locations } = useRealLocations()
  const save = useAction(() => api.patch(`/orders/${order.id}/`, {
    notes,
    lines: lines.map((l) => ({
      product: l.product, qty: l.qty, condition: l.condition, discount: l.discountText || '0',
      source_location: locations?.find((loc) => loc.code === l.source_location_code)?.id,
    })),
  }), { success: 'Sale updated.', onSuccess: onClose, toastErrors: false })
  return (
    <Dialog title={`Edit ${order.number}`} onClose={onClose} wide footer={<>
      <button type="button" className="btn btn-sec" onClick={onClose}>Cancel</button>
      <button type="button" className="btn btn-pri" disabled={!lines.length || save.isPending} onClick={() => save.mutateAsync(undefined).catch(setError)}>Save</button>
    </>}>
      <div className="tw">
        <table className="tbl tbl-cmp">
          <thead><tr><th>Product</th><th className="r">Price</th><th>Qty</th><th>Discount</th><th /></tr></thead>
          <tbody>
            {lines.map((l, i) => (
              <tr key={l.id}>
                <td><span className="mono" style={{ fontWeight: 600 }}>{l.product_code}</span> <CondTag condition={l.condition} /></td>
                <td className="r">{money(l.unit_price)}</td>
                <td><QtyStepper value={l.qty} min={1} onChange={(qty) => setLines(lines.map((x, j) => (j === i ? { ...x, qty } : x)))} /></td>
                <td style={{ width: 160 }}><MoneyInput value={l.discountText} onChange={(v) => setLines(lines.map((x, j) => (j === i ? { ...x, discountText: v } : x)))} /></td>
                <td><button type="button" className="x-btn" aria-label={`Remove ${l.product_code}`} onClick={() => setLines(lines.filter((_, j) => j !== i))}>×</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Field label="Notes">{(id) => <input id={id} className="inp" value={notes} onChange={(e) => setNotes(e.target.value)} />}</Field>
      <span className="sub">To add products or change the source, cancel this sale and make a new one.</span>
      {Boolean(error) && <ErrorBanner error={error} />}
    </Dialog>
  )
}
