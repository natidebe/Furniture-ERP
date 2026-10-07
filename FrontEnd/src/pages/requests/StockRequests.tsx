import { Link } from 'react-router-dom'
import { useApi, useRealLocations } from '../../api/hooks'
import type { Paginated, StockRequest } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { SearchInput } from '../../components/inputs'
import { DocLink, EthDate, Field, PageHeader, Pager, QueryState, StatusChip } from '../../components/ui'
import { label } from '../../lib/labels'
import { useFilters } from '../../lib/useFilters'

const STATUSES = ['pending', 'acknowledged', 'partially_released', 'released', 'closed', 'rejected', 'cancelled']

// P-30 Stock requests — the digital delivery paper from a branch to Pawlos. The storekeeper's
// default is the work queue: open requests, Pending first.
export default function StockRequests() {
  const { is } = useAuth()
  const store = is('storekeeper')
  const { values: f, set, setMany, page, setPage } = useFilters(['search', 'status', 'open', 'requesting_location'] as const, store ? { open: 'true' } : {})
  const { data: locations } = useRealLocations()
  const branches = locations?.filter((l) => l.type !== 'warehouse')
  const statusValue = f.open === 'true' ? 'open' : f.status
  const q = useApi<Paginated<StockRequest>>('/stock-requests/', {
    search: f.search, status: f.open === 'true' ? '' : f.status, open: f.open, requesting_location: f.requesting_location, page,
  }, { refetchInterval: store ? 30_000 : undefined })

  const setStatus = (v: string) => {
    if (v === 'open') setMany({ status: '', open: 'true' })
    else setMany({ open: '', status: v })
  }

  return (
    <main className="page">
      <PageHeader title="Stock requests" sub={store ? 'Requests from the branches to your warehouse' : 'Requests to Pawlos'}
        actions={is('salesperson', 'admin') && <Link className="btn btn-pri" to="/stock-requests/new">New stock request</Link>} />
      <div className="filters">
        <Field label="Search" className="fld-search">{(id) => <SearchInput id={id} value={f.search} onChange={(v) => set('search', v)} placeholder="Number, transaction, reference, customer or product code" />}</Field>
        <Field label="Status">{(id) => (
          <select id={id} className="inp" value={statusValue} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All</option>
            <option value="open">Open (work queue)</option>
            {STATUSES.map((s) => <option key={s} value={s}>{label(s)}</option>)}
          </select>
        )}</Field>
        {!is('salesperson') && (
          <Field label="Branch">{(id) => (
            <select id={id} className="inp" value={f.requesting_location} onChange={(e) => set('requesting_location', e.target.value)}>
              <option value="">All branches</option>{branches?.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          )}</Field>
        )}
      </div>
      <div className="tw">
        <QueryState query={q} empty={q.data?.results.length === 0} emptyHint={statusValue === 'open' ? 'No open requests 👍' : 'No requests match'}>
          <table className="tbl">
            <thead><tr><th>Number</th><th>Date</th><th>Branch</th><th>Customer / reference</th><th>Salesperson</th><th>Lines</th><th>Status</th><th className="r">Released</th><th>Transaction</th><th /></tr></thead>
            <tbody>
              {q.data?.results.map((r) => {
                const requested = r.lines.reduce((s, l) => s + l.qty_requested, 0)
                const released = r.lines.reduce((s, l) => s + l.qty_released, 0)
                return (
                  <tr key={r.id}>
                    <td><DocLink number={r.number} to={`/stock-requests/${r.id}`} strong /></td>
                    <td><EthDate value={r.created_at} /></td>
                    <td>{r.requesting_location_code}</td>
                    <td className="wrap">{r.customer_name ?? '—'}{r.reference && <div className="sub">{r.reference}</div>}</td>
                    <td>{r.salesperson_name}</td>
                    <td className="wrap mono" style={{ fontSize: 13 }}>{r.lines.map((l) => `${l.qty_requested} × ${l.product_code}`).join(', ')}</td>
                    <td><StatusChip kind="request" value={r.status} /></td>
                    <td className="r">{released} / {requested}</td>
                    <td>{r.transaction_number !== r.number ? <DocLink number={r.transaction_number} /> : <span className="muted">—</span>}</td>
                    <td className="r">
                      {store && (r.status === 'acknowledged' || r.status === 'partially_released') && <Link className="btn btn-pri btn-sm" to={`/stock-requests/${r.id}/release`}>Release</Link>}
                      {store && r.status === 'pending' && <Link className="btn btn-sec btn-sm" to={`/stock-requests/${r.id}`}>Open</Link>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </QueryState>
      </div>
      <Pager page={page} count={q.data?.count ?? 0} onPage={setPage} />
    </main>
  )
}
