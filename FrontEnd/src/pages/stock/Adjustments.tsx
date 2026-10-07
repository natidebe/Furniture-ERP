import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../../api/client'
import { useAction, useApi, useRealLocations } from '../../api/hooks'
import type { Adjustment, Paginated } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { ConfirmDialog, Dialog, ReasonDialog } from '../../components/Dialog'
import { ProductPicker } from '../../components/pickers'
import type { PickedProduct } from '../../components/pickers'
import { SearchInput } from '../../components/inputs'
import { CondTag, DocLink, EthDate, Field, PageHeader, Pager, QueryState, StatusChip } from '../../components/ui'
import { ADJUSTMENT_REASONS, label } from '../../lib/labels'
import { useFilters } from '../../lib/useFilters'

// P-24 Stock adjustments: counts, damage, loss, found items, opening balances, write-offs.
// Nothing moves until someone with approve_adjustments approves — never their own proposal
// (except an admin).
export default function Adjustments() {
  const { user, can, is } = useAuth()
  const [params, setParams] = useSearchParams()
  const { values: f, set, page, setPage } = useFilters(['search', 'status', 'location', 'reason'] as const)
  const { data: locations } = useRealLocations()
  const q = useApi<Paginated<Adjustment>>('/adjustments/', { ...f, page })
  const [deciding, setDeciding] = useState<{ a: Adjustment; approve: boolean } | null>(null)
  const creating = params.get('new') === '1'
  const setCreating = (on: boolean) => setParams((p) => { const n = new URLSearchParams(p); if (on) n.set('new', '1'); else n.delete('new'); return n })
  const decide = useAction(({ id, approve, note }: { id: number; approve: boolean; note: string }) =>
    api.post(`/adjustments/${id}/${approve ? 'approve' : 'reject'}/`, { note }), { toastErrors: false, success: 'Done.' })

  const canDecide = (a: Adjustment) => a.status === 'proposed' && can('approve_adjustments') && (is('admin') || a.proposed_by !== user?.id)

  return (
    <main className="page">
      <PageHeader title="Stock adjustments" sub="Counts, damage, loss, found items and opening balances"
        actions={<button type="button" className="btn btn-pri" onClick={() => setCreating(true)}>Propose adjustment</button>} />
      <div className="filters">
        <Field label="Search" className="fld-search">{(id) => <SearchInput id={id} value={f.search} onChange={(v) => set('search', v)} placeholder="ADJ number or product code" />}</Field>
        <Field label="Status">{(id) => (
          <select id={id} className="inp" value={f.status} onChange={(e) => set('status', e.target.value)}>
            <option value="">All</option><option value="proposed">Proposed</option><option value="approved">Approved</option><option value="rejected">Rejected</option>
          </select>
        )}</Field>
        {!is('storekeeper') && (
          <Field label="Location">{(id) => (
            <select id={id} className="inp" value={f.location} onChange={(e) => set('location', e.target.value)}>
              <option value="">All locations</option>
              {locations?.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          )}</Field>
        )}
        <Field label="Reason">{(id) => (
          <select id={id} className="inp" value={f.reason} onChange={(e) => set('reason', e.target.value)}>
            <option value="">All reasons</option>
            {ADJUSTMENT_REASONS.map((r) => <option key={r} value={r}>{label(r)}</option>)}
          </select>
        )}</Field>
      </div>
      <div className="tw">
        <QueryState query={q} empty={q.data?.results.length === 0} emptyHint="No adjustments">
          <table className="tbl">
            <thead><tr><th>Number</th><th>Date</th><th>Location</th><th>Product</th><th className="r">Change</th><th>Condition</th><th>Reason</th><th>Status</th><th>Proposed by</th><th>Decided by</th><th /></tr></thead>
            <tbody>
              {q.data?.results.map((a) => (
                <tr key={a.id}>
                  <td className="mono" style={{ fontSize: 13 }}>{a.number}</td>
                  <td><EthDate value={a.proposed_at} /></td>
                  <td>{a.location_code}</td>
                  <td><Link className="mono" to={`/products/${a.product}`}>{a.product_code}</Link></td>
                  <td className="r" style={{ fontWeight: 700, color: a.qty_delta < 0 ? 'var(--red-fg)' : 'var(--green-fg)' }}>{a.qty_delta > 0 ? '+' : ''}{a.qty_delta}</td>
                  <td><CondTag condition={a.condition} /></td>
                  <td className="wrap">{label(a.reason)}{a.note && <div className="sub">{a.note}</div>}</td>
                  <td>
                    <StatusChip kind="adjustment" value={a.status} />
                    {a.status === 'proposed' && <div className="sub">Waiting for approval</div>}
                    {a.decision_note && <div className="sub">{a.decision_note}</div>}
                  </td>
                  <td>{a.proposed_by_name}</td>
                  <td>{a.decided_by_name ?? '—'}{a.movement_number && <div><DocLink number={a.movement_number} /></div>}</td>
                  <td className="r">
                    {canDecide(a) && (
                      <div className="row" style={{ flexWrap: 'nowrap', justifyContent: 'flex-end' }}>
                        <button type="button" className="btn btn-dan btn-sm" onClick={() => setDeciding({ a, approve: false })}>Reject…</button>
                        <button type="button" className="btn btn-pri btn-sm" onClick={() => setDeciding({ a, approve: true })}>Approve</button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </QueryState>
      </div>
      <Pager page={page} count={q.data?.count ?? 0} onPage={setPage} />
      {creating && <ProposeAdjustment onClose={() => setCreating(false)} />}
      {deciding?.approve && (
        <ConfirmDialog title="Approve adjustment"
          message={<>Approve <span className="mono">{deciding.a.number}</span>: <strong>{deciding.a.qty_delta > 0 ? '+' : ''}{deciding.a.qty_delta} × {deciding.a.product_code}</strong> ({deciding.a.condition}) at {deciding.a.location_code}? The stock changes now.</>}
          confirmLabel="Approve" onConfirm={() => decide.mutateAsync({ id: deciding.a.id, approve: true, note: '' })} onClose={() => setDeciding(null)} />
      )}
      {deciding && !deciding.approve && (
        <ReasonDialog title="Reject adjustment" label="Note"
          message={<>Reject <span className="mono">{deciding.a.number}</span>? Nothing moves.</>}
          confirmLabel="Reject" onConfirm={(note) => decide.mutateAsync({ id: deciding.a.id, approve: false, note })} onClose={() => setDeciding(null)} />
      )}
    </main>
  )
}

function ProposeAdjustment({ onClose }: { onClose: () => void }) {
  const { user, is } = useAuth()
  const { data: locations } = useRealLocations()
  const [location, setLocation] = useState(is('storekeeper') ? String(user?.home_location ?? '') : '')
  const [product, setProduct] = useState<PickedProduct | null>(null)
  const [direction, setDirection] = useState<'remove' | 'add'>('remove')
  const [qty, setQty] = useState('1')
  const [condition, setCondition] = useState('new')
  const [reason, setReason] = useState('count')
  const [note, setNote] = useState('')
  const [confirm, setConfirm] = useState(false)
  const loc = locations?.find((l) => String(l.id) === location)
  const delta = (direction === 'remove' ? -1 : 1) * Number(qty || 0)
  const save = useAction(() => api.post<Adjustment>('/adjustments/', {
    location: Number(location), product: product!.id, qty_delta: delta, condition, reason, note,
  }), { success: (a) => `${(a as Adjustment).number} proposed — waiting for approval.`, onSuccess: onClose, toastErrors: false })

  return (
    <Dialog title="Propose adjustment" onClose={onClose} wide footer={<>
      <button type="button" className="btn btn-sec" onClick={onClose}>Cancel</button>
      <button type="button" className="btn btn-pri" disabled={!location || !product || !Number(qty)} onClick={() => setConfirm(true)}>Propose</button>
    </>}>
      <div className="form-grid">
        <Field label="Location">{(id) => (
          <select id={id} className="inp" value={location} disabled={is('storekeeper')} onChange={(e) => setLocation(e.target.value)}>
            <option value="">Choose…</option>
            {locations?.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
          </select>
        )}</Field>
        <Field label="Product">{(id) => product
          ? <div className="row" style={{ height: 42 }}><span className="mono" style={{ fontWeight: 600 }}>{product.code}</span> {product.name} <button type="button" className="btn btn-q btn-sm" onClick={() => setProduct(null)}>Change</button></div>
          : <ProductPicker id={id} onPick={setProduct} stockAt={loc ? [loc.code] : []} />}</Field>
      </div>
      {product && loc && (
        <span className="sub">At {loc.code}: {product.stock[loc.code]?.on_hand ?? 0} on hand · {product.stock[loc.code]?.display ?? 0} display · {product.stock[loc.code]?.damaged ?? 0} damaged · {product.stock[loc.code]?.available ?? 0} free</span>
      )}
      <div className="form-grid">
        <Field label="Change">{() => (
          <div className="row" style={{ flexWrap: 'nowrap', gap: 8 }}>
            <div className="seg" role="group" aria-label="Add or remove">
              <button type="button" aria-pressed={direction === 'remove'} onClick={() => setDirection('remove')}>− Remove</button>
              <button type="button" aria-pressed={direction === 'add'} onClick={() => setDirection('add')}>+ Add</button>
            </div>
            <input className="inp num" aria-label="Quantity" inputMode="numeric" style={{ width: 90 }} value={qty} onChange={(e) => setQty(e.target.value.replace(/\D/g, ''))} />
          </div>
        )}</Field>
        <Field label="Condition" hint="e.g. write off 2 damaged chairs: remove 2, damaged">{(id) => (
          <select id={id} className="inp" value={condition} onChange={(e) => setCondition(e.target.value)}>
            <option value="new">New</option><option value="display">Display</option><option value="damaged">Damaged</option>
          </select>
        )}</Field>
        <Field label="Reason">{(id) => (
          <select id={id} className="inp" value={reason} onChange={(e) => setReason(e.target.value)}>
            {ADJUSTMENT_REASONS.map((r) => <option key={r} value={r}>{label(r)}</option>)}
          </select>
        )}</Field>
      </div>
      <Field label="Note">{(id) => <input id={id} className="inp" value={note} onChange={(e) => setNote(e.target.value)} placeholder="What happened" maxLength={255} />}</Field>
      <span className="sub">Nothing moves until the accountant approves.</span>
      {confirm && product && (
        <ConfirmDialog title="Propose adjustment"
          message={<>Propose <strong>{delta > 0 ? '+' : ''}{delta} × {product.code}</strong> ({condition}) at {loc?.name}, reason {label(reason)}?</>}
          confirmLabel="Propose" onConfirm={() => save.mutateAsync(undefined)} onClose={() => setConfirm(false)} />
      )}
    </Dialog>
  )
}
