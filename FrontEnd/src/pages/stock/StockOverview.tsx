import { Link } from 'react-router-dom'
import { download, errorMessage } from '../../api/client'
import { useApi, useCategories } from '../../api/hooks'
import type { StockSummary } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { SearchInput } from '../../components/inputs'
import { Field, PageHeader, Pager, QueryState } from '../../components/ui'
import { useToast } from '../../components/Toast'
import { useFilters } from '../../lib/useFilters'

const COLUMN_NAME: Record<string, string> = { PIA: 'Piassa', 'PIA-UG': 'Underground', DEN: 'Denbel', PAW: 'Pawlos' }

// P-20 Stock overview (the client's "Current stock" table) and P-21 Low stock.
// Total includes In transit (D7); Sellable leaves out display and damaged (D15).
export default function StockOverview({ lowOnly = false }: { lowOnly?: boolean }) {
  const { can, is } = useAuth()
  const toast = useToast()
  const { values: f, set, page, setPage } = useFilters(['search', 'category', 'low'] as const)
  const low = lowOnly || f.low === 'true'
  const { data: categories } = useCategories()
  const q = useApi<StockSummary>('/stock/summary/', { search: f.search, category: f.category, low: low ? 'true' : '', page })
  const lowCount = useApi<StockSummary>('/stock/summary/', { low: 'true', page_size: 1 })
  const columns = (q.data?.locations ?? []).filter((l) => l.code !== 'TRANSIT')

  const exportExcel = () => download('/reports/stock/', { format: 'xlsx', category: f.category }, 'stock.xlsx')
    .catch((e) => toast.show(errorMessage(e), 'error'))

  return (
    <main className="page">
      {lowOnly && <Link to="/stock" style={{ fontSize: 14 }}>← Current stock</Link>}
      <PageHeader title={lowOnly ? 'Low stock' : 'Current stock'}
        sub={lowOnly ? 'Products whose sellable stock is below their minimum' : `All locations · ${q.data?.count ?? '…'} products`}
        actions={<>
          {!lowOnly && <Link className="btn btn-sec" to="/stock/low">Low stock ({lowCount.data?.count ?? '…'})</Link>}
          {is('accountant', 'admin') && <Link className="btn btn-sec" to="/transfers/new">New transfer</Link>}
          {can('export_reports') && <button type="button" className="btn btn-sec" onClick={exportExcel}>Export Excel</button>}
        </>} />
      <div className="filters">
        <Field label="Search" className="fld-search">{(id) => <SearchInput id={id} value={f.search} onChange={(v) => set('search', v)} placeholder="Code or name" />}</Field>
        <Field label="Category">{(id) => (
          <select id={id} className="inp" value={f.category} onChange={(e) => set('category', e.target.value)}>
            <option value="">All categories</option>
            {categories?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        )}</Field>
        {!lowOnly && <label className="check" style={{ height: 42 }}><input type="checkbox" checked={low} onChange={(e) => set('low', e.target.checked ? 'true' : '')} />Low stock only</label>}
        <div className="row sub" style={{ marginLeft: 'auto', gap: 14, fontSize: 13 }}>
          <span><span className="tag t-blue">5 res</span> reserved for requests</span>
          <span><span className="tag t-cond">1 disp</span> <span className="tag t-cond">1 dmg</span> display / damaged</span>
          <span className="row" style={{ gap: 6 }}><span style={{ width: 14, height: 14, background: '#fffaf0', border: '1px solid var(--amber-bg)', borderRadius: 3 }} />Sellable below minimum</span>
        </div>
      </div>
      <div className="tw">
        <QueryState query={q} empty={q.data?.results.length === 0} emptyHint={low ? 'Nothing is below its minimum 👍' : 'No products match'}>
          <table className="tbl">
            <thead>
              <tr>
                <th>Product</th>
                {columns.map((l) => <th key={l.code} className="r">{COLUMN_NAME[l.code] ?? l.name}</th>)}
                <th className="r">In transit</th><th className="r">Total</th><th className="r">Sellable</th><th className="r">Min</th>
                {lowOnly && <th className="r">Short by</th>}
              </tr>
            </thead>
            <tbody>
              {q.data?.results.map((r) => (
                <tr key={r.product} className={r.low_stock ? 'hl' : undefined}>
                  <td><Link className="mono" to={`/products/${r.product}`} style={{ fontWeight: 600 }}>{r.code}</Link> <span>{r.name}</span></td>
                  {columns.map((l) => {
                    const c = r.stock[l.code]
                    if (!c) return <td key={l.code} className="r" style={{ color: 'var(--faint)' }}>0</td>
                    return (
                      <td key={l.code} className="r" title={`Available: ${c.available}`}>
                        <span className="row" style={{ justifyContent: 'flex-end', gap: 4, flexWrap: 'nowrap' }}>
                          {c.reserved > 0 && <span className="tag t-blue">{c.reserved} res</span>}
                          {c.display > 0 && <span className="tag t-cond">{c.display} disp</span>}
                          {c.damaged > 0 && <span className="tag t-cond">{c.damaged} dmg</span>}
                          <span style={{ color: c.on_hand ? undefined : 'var(--faint)', minWidth: 24 }}>{c.on_hand}</span>
                        </span>
                      </td>
                    )
                  })}
                  <td className="r" style={r.in_transit ? { color: 'var(--link)', fontWeight: 600 } : { color: 'var(--faint)' }}>{r.in_transit}</td>
                  <td className="r" style={{ fontWeight: 700 }}>{r.total}</td>
                  <td className="r" style={r.low_stock ? { fontWeight: 700, color: 'var(--amber-fg)' } : { fontWeight: 600 }}>{r.total_new}</td>
                  <td className="r sub">{r.min_stock}</td>
                  {lowOnly && <td className="r" style={{ fontWeight: 600, color: 'var(--amber-fg)' }}>{Math.max(0, r.min_stock - r.total_new)}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </QueryState>
      </div>
      <Pager page={page} count={q.data?.count ?? 0} onPage={setPage} note="Total includes goods in transit. Sellable leaves out display and damaged pieces. Hover a cell for the available quantity." />
    </main>
  )
}
