import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import { useAction, useApi, useRealLocations } from '../../api/hooks'
import type { ConditionChange, Paginated } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { ConfirmDialog, Dialog } from '../../components/Dialog'
import { ProductPicker } from '../../components/pickers'
import type { PickedProduct } from '../../components/pickers'
import { QtyStepper } from '../../components/inputs'
import { CondTag, EthDate, Field, PageHeader, Pager, QueryState } from '../../components/ui'
import { label } from '../../lib/labels'
import { useFilters } from '../../lib/useFilters'

type Cond = 'new' | 'display' | 'damaged'
const QUICK: { text: string; from: Cond; to: Cond }[] = [
  { text: 'Put on display', from: 'new', to: 'display' },
  { text: 'Mark damaged', from: 'new', to: 'damaged' },
  { text: 'Back to new', from: 'display', to: 'new' },
]

// P-27 Display & damaged stock (D15). These pieces stay in the location's total but are never
// reserved or sold as new: sold as such on New sale, written off on Adjustments, sent for repair
// with a transfer.
export default function DisplayDamaged() {
  const { is } = useAuth()
  const { values: f, set, page, setPage } = useFilters(['location', 'to_condition'] as const)
  const { data: locations } = useRealLocations()
  const q = useApi<Paginated<ConditionChange>>('/stock/condition-changes/', { ...f, page })
  const [form, setForm] = useState<{ from: Cond; to: Cond } | null>(null)

  return (
    <main className="page">
      <PageHeader title="Display & damaged stock" sub="Pieces on display or damaged stay in the total but are not sold as new"
        actions={<>
          {QUICK.map((qa) => <button key={qa.text} type="button" className="btn btn-sec" onClick={() => setForm({ from: qa.from, to: qa.to })}>{qa.text}</button>)}
          <button type="button" className="btn btn-pri" onClick={() => setForm({ from: 'new', to: 'display' })}>New change</button>
        </>} />
      <div className="filters">
        {is('accountant', 'admin') && (
          <Field label="Location">{(id) => (
            <select id={id} className="inp" value={f.location} onChange={(e) => set('location', e.target.value)}>
              <option value="">All locations</option>{locations?.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          )}</Field>
        )}
        <Field label="Changed to">{(id) => (
          <select id={id} className="inp" value={f.to_condition} onChange={(e) => set('to_condition', e.target.value)}>
            <option value="">Any</option><option value="display">Display</option><option value="damaged">Damaged</option><option value="new">New</option>
          </select>
        )}</Field>
        <span className="sub" style={{ marginLeft: 'auto', alignSelf: 'center' }}>Write off on <Link to="/adjustments">Adjustments</Link> · send for repair with a <Link to="/transfers">transfer</Link></span>
      </div>
      <div className="tw">
        <QueryState query={q} empty={q.data?.results.length === 0} emptyHint="No condition changes yet">
          <table className="tbl">
            <thead><tr><th>Number</th><th>Date</th><th>Location</th><th>Product</th><th className="r">Qty</th><th>From → to</th><th>Reason</th><th>Who</th></tr></thead>
            <tbody>
              {q.data?.results.map((c) => (
                <tr key={c.id}>
                  <td className="mono" style={{ fontSize: 13 }}>{c.number}</td>
                  <td><EthDate value={c.occurred_at} /></td>
                  <td>{c.location_code}</td>
                  <td><Link className="mono" to={`/products/${c.product}`}>{c.product_code}</Link></td>
                  <td className="r" style={{ fontWeight: 600 }}>{c.qty}</td>
                  <td><CondTag condition={c.from_condition} /> → <CondTag condition={c.to_condition} /></td>
                  <td className="wrap">{c.reason}</td>
                  <td>{c.person_name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </QueryState>
      </div>
      <Pager page={page} count={q.data?.count ?? 0} onPage={setPage} />
      {form && <ChangeCondition initial={form} onClose={() => setForm(null)} />}
    </main>
  )
}

function ChangeCondition({ initial, onClose }: { initial: { from: Cond; to: Cond }; onClose: () => void }) {
  const { user, is } = useAuth()
  const { data: locations } = useRealLocations()
  const office = is('accountant', 'admin')
  const [location, setLocation] = useState(office ? '' : String(user?.home_location ?? ''))
  const [product, setProduct] = useState<PickedProduct | null>(null)
  const [from, setFrom] = useState<Cond>(initial.from)
  const [to, setTo] = useState<Cond>(initial.to)
  const [qty, setQty] = useState(1)
  const [reason, setReason] = useState('')
  const [confirm, setConfirm] = useState(false)
  const loc = locations?.find((l) => String(l.id) === location)
  const cell = product && loc ? product.stock[loc.code] : undefined
  const free = !cell ? 0 : from === 'new' ? cell.available : from === 'display' ? cell.display : cell.damaged
  const save = useAction(() => api.post<ConditionChange>('/stock/condition-changes/', {
    product: product!.id, location: Number(location), qty, from_condition: from, to_condition: to, reason,
  }), { success: (c) => `${(c as ConditionChange).number} saved.`, onSuccess: onClose, toastErrors: false })

  return (
    <Dialog title="Change condition" onClose={onClose} wide footer={<>
      <button type="button" className="btn btn-sec" onClick={onClose}>Cancel</button>
      <button type="button" className="btn btn-pri" disabled={!product || !location || from === to || !reason.trim() || qty < 1 || qty > free} onClick={() => setConfirm(true)}>Save change</button>
    </>}>
      <div className="form-grid">
        <Field label="Location">{(id) => (
          <select id={id} className="inp" value={location} disabled={!office} onChange={(e) => setLocation(e.target.value)}>
            <option value="">Choose…</option>{locations?.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
          </select>
        )}</Field>
        <Field label="Product">{(id) => product
          ? <div className="row" style={{ height: 42 }}><span className="mono" style={{ fontWeight: 600 }}>{product.code}</span> {product.name} <button type="button" className="btn btn-q btn-sm" onClick={() => setProduct(null)}>Change</button></div>
          : <ProductPicker id={id} onPick={setProduct} stockAt={loc ? [loc.code] : []} />}</Field>
      </div>
      <div className="form-grid">
        <Field label="From">{(id) => (
          <select id={id} className="inp" value={from} onChange={(e) => setFrom(e.target.value as Cond)}>
            <option value="new">New</option><option value="display">Display</option><option value="damaged">Damaged</option>
          </select>
        )}</Field>
        <Field label="To" error={from === to ? 'Choose a different condition.' : undefined}>{(id) => (
          <select id={id} className="inp" value={to} onChange={(e) => setTo(e.target.value as Cond)}>
            <option value="display">Display</option><option value="damaged">Damaged</option><option value="new">New</option>
          </select>
        )}</Field>
        <Field label="Quantity" hint={product && loc ? `${free} ${label(from).toLowerCase()} free at ${loc.code}` : undefined}>{(id) => <QtyStepper id={id} value={qty} min={1} max={product && loc ? free : undefined} onChange={setQty} />}</Field>
      </div>
      <Field label="Reason (required)">{(id) => <input id={id} className="inp" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Scratched in delivery; on the showroom floor" maxLength={255} />}</Field>
      {confirm && product && (
        <ConfirmDialog title="Change condition" message={<>Change <strong>{qty} × {product.code}</strong> at {loc?.name} from {label(from)} to {label(to)}?</>}
          confirmLabel="Change" onConfirm={() => save.mutateAsync(undefined)} onClose={() => setConfirm(false)} />
      )}
    </Dialog>
  )
}
