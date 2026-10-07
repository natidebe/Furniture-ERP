import { Link } from 'react-router-dom'
import { useApi, useCategories } from '../../api/hooks'
import type { Paginated, Product } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { SearchInput } from '../../components/inputs'
import { Field, PageHeader, Pager, QueryState, StatusChip } from '../../components/ui'
import { money } from '../../lib/format'
import { useFilters } from '../../lib/useFilters'

// P-10 Products. Admins add and import; everyone else reads.
export default function Products() {
  const { is } = useAuth()
  const { values: f, set, page, setPage } = useFilters(['search', 'category', 'is_active', 'ordering'] as const, { is_active: 'true', ordering: 'code' })
  const { data: categories } = useCategories()
  const q = useApi<Paginated<Product>>('/products/', { ...f, page })
  return (
    <main className="page">
      <PageHeader title="Products" sub={q.data ? `${q.data.count} products` : ' '}
        actions={is('admin') && <><Link className="btn btn-sec" to="/products/import">Import products</Link><Link className="btn btn-pri" to="/products/new">New product</Link></>} />
      <div className="filters">
        <Field label="Search" className="fld-search">{(id) => <SearchInput id={id} value={f.search} onChange={(v) => set('search', v)} placeholder="Code or name" />}</Field>
        <Field label="Category">{(id) => (
          <select id={id} className="inp" value={f.category} onChange={(e) => set('category', e.target.value)}>
            <option value="">All categories</option>
            {categories?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        )}</Field>
        <Field label="Status">{(id) => (
          <select id={id} className="inp" value={f.is_active} onChange={(e) => set('is_active', e.target.value)}>
            <option value="true">Active</option><option value="false">Inactive</option><option value="">All</option>
          </select>
        )}</Field>
        <Field label="Sort by">{(id) => (
          <select id={id} className="inp" value={f.ordering} onChange={(e) => set('ordering', e.target.value)}>
            <option value="code">Code</option><option value="name">Name</option><option value="selling_price">Price</option>
          </select>
        )}</Field>
      </div>
      <div className="tw">
        <QueryState query={q} empty={q.data?.results.length === 0} emptyHint="No products match these filters">
          <table className="tbl">
            <thead><tr><th>Code</th><th>Name</th><th>Category</th><th>Unit</th><th className="r">Selling price</th><th className="r">Wholesale</th><th className="r">Min stock</th><th>Status</th></tr></thead>
            <tbody>
              {q.data?.results.map((p) => (
                <tr key={p.id}>
                  <td><Link className="mono" to={`/products/${p.id}`} style={{ fontWeight: 600 }}>{p.code}</Link></td>
                  <td><Link to={`/products/${p.id}`} style={{ color: 'var(--ink)' }}>{p.name}</Link></td>
                  <td>{p.category_name}</td>
                  <td>{p.unit_symbol}</td>
                  <td className="r">{money(p.selling_price)}</td>
                  <td className="r" style={{ color: p.wholesale_price ? undefined : 'var(--faint)' }}>{money(p.wholesale_price)}</td>
                  <td className="r">{p.min_stock}</td>
                  <td><StatusChip kind="active" value={String(p.is_active)} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </QueryState>
      </div>
      <Pager page={page} count={q.data?.count ?? 0} onPage={setPage} note="Prices in ETB. An empty wholesale price means resellers pay the selling price." />
    </main>
  )
}
