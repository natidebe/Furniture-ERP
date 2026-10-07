import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../../api/client'
import { useAction, useApi, useRealLocations } from '../../api/hooks'
import type { GoodsReceipt, Paginated } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { ConfirmDialog, Dialog } from '../../components/Dialog'
import { EthDatePicker } from '../../components/EthDatePicker'
import { LinesEditor, linesSummary } from '../../components/LinesEditor'
import type { EditorLine } from '../../components/LinesEditor'
import { SearchInput } from '../../components/inputs'
import { EthDate, Field, PageHeader, Pager, QueryState } from '../../components/ui'
import { useFilters } from '../../lib/useFilters'

// P-23 Goods receipts — imported goods arriving, usually at Pawlos (Q1).
export default function GoodsReceipts() {
  const [params, setParams] = useSearchParams()
  const { values: f, set, page, setPage } = useFilters(['search', 'location'] as const)
  const { is } = useAuth()
  const { data: locations } = useRealLocations()
  const q = useApi<Paginated<GoodsReceipt>>('/goods-receipts/', { ...f, page })
  const [open, setOpen] = useState<GoodsReceipt | null>(null)
  const creating = params.get('new') === '1'
  const setCreating = (on: boolean) => setParams((p) => { const n = new URLSearchParams(p); if (on) n.set('new', '1'); else n.delete('new'); return n })

  return (
    <main className="page">
      <PageHeader title="Goods receipts" sub="Imported goods arriving at a location"
        actions={<button type="button" className="btn btn-pri" onClick={() => setCreating(true)}>New goods receipt</button>} />
      <div className="filters">
        <Field label="Search" className="fld-search">{(id) => <SearchInput id={id} value={f.search} onChange={(v) => set('search', v)} placeholder="GR number or reference" />}</Field>
        {!is('storekeeper') && (
          <Field label="Location">{(id) => (
            <select id={id} className="inp" value={f.location} onChange={(e) => set('location', e.target.value)}>
              <option value="">All locations</option>
              {locations?.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          )}</Field>
        )}
      </div>
      <div className="tw">
        <QueryState query={q} empty={q.data?.results.length === 0} emptyHint="No goods receipts yet">
          <table className="tbl">
            <thead><tr><th>Number</th><th>Date received</th><th>Location</th><th>Reference</th><th>Lines</th><th>Received by</th></tr></thead>
            <tbody>
              {q.data?.results.map((g) => (
                <tr key={g.id}>
                  <td><button type="button" className="btn btn-q mono" style={{ padding: 0, height: 'auto', fontSize: 13 }} onClick={() => setOpen(g)}>{g.number}</button></td>
                  <td><EthDate value={g.received_at} /></td>
                  <td>{g.location_code}</td>
                  <td>{g.reference || '—'}</td>
                  <td className="wrap">{g.lines.map((l) => `${l.qty} × ${l.product_code}`).join(', ')}</td>
                  <td>{g.received_by_name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </QueryState>
      </div>
      <Pager page={page} count={q.data?.count ?? 0} onPage={setPage} />
      {creating && <NewReceipt onClose={() => setCreating(false)} />}
      {open && (
        <Dialog title={open.number} onClose={() => setOpen(null)} wide>
          <dl className="dl">
            <dt>Location</dt><dd>{open.location_code}</dd>
            <dt>Received</dt><dd><EthDate value={open.received_at} /> by {open.received_by_name}</dd>
            <dt>Reference</dt><dd>{open.reference || '—'}</dd>
            {open.note && <><dt>Note</dt><dd>{open.note}</dd></>}
          </dl>
          <div className="tw"><table className="tbl"><thead><tr><th>Product</th><th className="r">Qty</th></tr></thead><tbody>
            {open.lines.map((l) => <tr key={l.product}><td><Link className="mono" to={`/products/${l.product}`}>{l.product_code}</Link> {l.product_name}</td><td className="r">{l.qty}</td></tr>)}
          </tbody></table></div>
          <Link to={`/movements?search=${open.number}`}>Movements of this receipt</Link>
        </Dialog>
      )}
    </main>
  )
}

function NewReceipt({ onClose }: { onClose: () => void }) {
  const { user, is } = useAuth()
  const { data: locations } = useRealLocations()
  const paw = locations?.find((l) => l.code === 'PAW')
  const [location, setLocation] = useState<string>('')
  const [reference, setReference] = useState('')
  const [receivedAt, setReceivedAt] = useState('')
  const [note, setNote] = useState('')
  const [lines, setLines] = useState<EditorLine[]>([])
  const [confirm, setConfirm] = useState(false)
  const target = is('storekeeper') ? locations?.find((l) => l.id === user?.home_location) : locations?.find((l) => String(l.id) === location) ?? paw
  const save = useAction(() => api.post<GoodsReceipt>('/goods-receipts/', {
    location: target?.id, reference, note,
    ...(receivedAt ? { received_at: `${receivedAt}T12:00:00+03:00` } : {}),
    lines: lines.map((l) => ({ product: l.product.id, qty: l.qty })),
  }), { success: (g) => `${(g as GoodsReceipt).number} saved — stock added to ${target?.code}.`, onSuccess: onClose, toastErrors: false })

  return (
    <Dialog title="New goods receipt" onClose={onClose} wide footer={<>
      <button type="button" className="btn btn-sec" onClick={onClose}>Cancel</button>
      <button type="button" className="btn btn-pri" disabled={!lines.length || !target} onClick={() => setConfirm(true)}>Receive goods</button>
    </>}>
      <div className="form-grid">
        <Field label="Location">{(id) => is('storekeeper')
          ? <input id={id} className="inp" readOnly value={target?.name ?? ''} />
          : (
            <select id={id} className="inp" value={location || String(paw?.id ?? '')} onChange={(e) => setLocation(e.target.value)}>
              {locations?.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          )}</Field>
        <Field label="Reference" hint="Container, shipment or invoice number">{(id) => <input id={id} className="inp" value={reference} onChange={(e) => setReference(e.target.value)} />}</Field>
        <Field label="Date received" hint="Empty: now">{(id) => <EthDatePicker id={id} value={receivedAt} onChange={setReceivedAt} placeholder="Today" />}</Field>
      </div>
      <LinesEditor lines={lines} onChange={setLines} stockAt={target ? [target.code] : []} />
      <Field label="Note (optional)">{(id) => <input id={id} className="inp" value={note} onChange={(e) => setNote(e.target.value)} />}</Field>
      {confirm && (
        <ConfirmDialog title="Receive goods" message={<>Add <strong>{linesSummary(lines)}</strong> to {target?.name}?</>}
          confirmLabel="Add to stock" onConfirm={() => save.mutateAsync(undefined)} onClose={() => setConfirm(false)} />
      )}
    </Dialog>
  )
}
