import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import { useAction, useApi, useRealLocations } from '../../api/hooks'
import type { Movement, Paginated } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { EthDatePicker } from '../../components/EthDatePicker'
import { ReasonDialog } from '../../components/Dialog'
import { SearchInput } from '../../components/inputs'
import { CondTag, DocLink, EthDate, Field, PageHeader, Pager, QueryState } from '../../components/ui'
import { MOVEMENT_TYPES, label } from '../../lib/labels'
import { useFilters } from '../../lib/useFilters'

// P-22 Stock movements — the ledger. Only goods-receipt movements can be reversed here
// (correct_transactions); everything else is corrected through its own document.
export default function Movements() {
  const { can, is } = useAuth()
  const { values: f, set, page, setPage } = useFilters(['search', 'product', 'location', 'type', 'transaction', 'from', 'to'] as const)
  const { data: locations } = useRealLocations()
  const q = useApi<Paginated<Movement>>('/stock/movements/', { ...f, page })
  const [reversing, setReversing] = useState<Movement | null>(null)
  const reverse = useAction(({ id, reason }: { id: number; reason: string }) => api.post(`/stock/movements/${id}/reverse/`, { reason }),
    { success: 'Movement reversed.', toastErrors: false })

  return (
    <main className="page">
      <PageHeader title="Stock movements" sub={is('storekeeper') ? 'At your location' : 'Every location'} />
      <div className="filters">
        <Field label="Search" className="fld-search">{(id) => <SearchInput id={id} value={f.search} onChange={(v) => set('search', v)} placeholder="MV / transaction number or product code" />}</Field>
        {!is('storekeeper') && (
          <Field label="Location">{(id) => (
            <select id={id} className="inp" value={f.location} onChange={(e) => set('location', e.target.value)}>
              <option value="">All locations</option>
              {locations?.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          )}</Field>
        )}
        <Field label="Type">{(id) => (
          <select id={id} className="inp" value={f.type} onChange={(e) => set('type', e.target.value)}>
            <option value="">All types</option>
            {MOVEMENT_TYPES.map((t) => <option key={t} value={t}>{label(t)}</option>)}
          </select>
        )}</Field>
        <Field label="From" style={{ flex: '0 1 240px' }}>{(id) => <EthDatePicker id={id} value={f.from} onChange={(v) => set('from', v)} />}</Field>
        <Field label="To" style={{ flex: '0 1 240px' }}>{(id) => <EthDatePicker id={id} value={f.to} onChange={(v) => set('to', v)} />}</Field>
        {f.product && <button type="button" className="btn btn-q" onClick={() => set('product', '')}>Clear product filter ×</button>}
      </div>
      <div className="tw">
        <QueryState query={q} empty={q.data?.results.length === 0} emptyHint="No movements match">
          <table className="tbl">
            <thead><tr><th>Date</th><th>Number</th><th>Type</th><th>Condition</th><th>Product</th><th className="r">Qty</th><th>From</th><th>To</th><th>Customer</th><th>Person</th><th>Transaction</th><th>Note</th>{can('correct_transactions') && <th />}</tr></thead>
            <tbody>
              {q.data?.results.map((m) => (
                <tr key={m.id}>
                  <td><EthDate value={m.occurred_at} /></td>
                  <td className="mono" style={{ fontSize: 13 }}>{m.number}</td>
                  <td>{label(m.type)}{m.reverses_number && <div className="sub">reverses {m.reverses_number}</div>}</td>
                  <td><CondTag condition={m.condition ?? 'new'} /></td>
                  <td><Link className="mono" to={`/products/${m.product}`}>{m.product_code}</Link></td>
                  <td className="r" style={{ fontWeight: 600 }}>{m.qty}</td>
                  <td>{m.from_location_code ?? '—'}</td>
                  <td>{m.to_location_code ?? '—'}</td>
                  <td>{m.customer_name ?? '—'}</td>
                  <td>{m.person_name}</td>
                  <td><DocLink number={m.transaction_number || m.reference_id} /></td>
                  <td className="wrap sub">{m.note}</td>
                  {can('correct_transactions') && (
                    <td>{m.type === 'receipt' && !m.reverses_number && <button type="button" className="btn btn-dan btn-sm" onClick={() => setReversing(m)}>Reverse…</button>}</td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </QueryState>
      </div>
      <Pager page={page} count={q.data?.count ?? 0} onPage={setPage} />
      {reversing && (
        <ReasonDialog title="Reverse goods receipt movement"
          message={<>Reverse <span className="mono">{reversing.number}</span>: take {reversing.qty} × {reversing.product_code} back out of {reversing.to_location_code}? A reversal movement is written; the original stays in the ledger.</>}
          confirmLabel="Reverse movement" onConfirm={(reason) => reverse.mutateAsync({ id: reversing.id, reason })} onClose={() => setReversing(null)} />
      )}
    </main>
  )
}
