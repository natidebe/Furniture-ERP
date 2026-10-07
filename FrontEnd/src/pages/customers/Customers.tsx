import { Link } from 'react-router-dom'
import { useApi } from '../../api/hooks'
import type { Customer, Paginated } from '../../api/types'
import { SearchInput } from '../../components/inputs'
import { Field, PageHeader, Pager, QueryState } from '../../components/ui'
import { money } from '../../lib/format'
import { CUSTOMER_TYPES, label } from '../../lib/labels'
import { useFilters } from '../../lib/useFilters'

// P-60 Customers, with what each one owes and who is over their limit.
export default function Customers() {
  const { values: f, set, setMany, page, setPage } = useFilters(['search', 'type', 'city', 'credit_allowed', 'has_balance', 'over_limit', 'is_active', 'ordering'] as const, { is_active: 'true' })
  const q = useApi<Paginated<Customer>>('/customers/', { ...f, page })
  return (
    <main className="page">
      <PageHeader title="Customers & credit" sub={q.data ? `${q.data.count} customers` : ' '}
        actions={<Link className="btn btn-pri" to="/customers/new">New customer</Link>} />
      <div className="filters">
        <Field label="Search" className="fld-search">{(id) => <SearchInput id={id} value={f.search} onChange={(v) => set('search', v)} placeholder="Name, phone or shop" />}</Field>
        <Field label="Type">{(id) => (
          <select id={id} className="inp" value={f.type} onChange={(e) => set('type', e.target.value)}>
            <option value="">All types</option>{CUSTOMER_TYPES.map((t) => <option key={t} value={t}>{label(t)}</option>)}
          </select>
        )}</Field>
        <Field label="City">{(id) => <SearchInput id={id} value={f.city} onChange={(v) => set('city', v)} placeholder="Exact city" />}</Field>
        <Field label="Credit">{(id) => (
          <select id={id} className="inp" value={f.credit_allowed} onChange={(e) => set('credit_allowed', e.target.value)}>
            <option value="">Any</option><option value="true">Allowed</option><option value="false">Not allowed</option>
          </select>
        )}</Field>
        <Field label="Balance">{(id) => (
          <select id={id} className="inp" value={f.over_limit === 'true' ? 'over' : f.has_balance === 'true' ? 'owes' : ''}
            onChange={(e) => setMany({ has_balance: e.target.value === 'owes' ? 'true' : '', over_limit: e.target.value === 'over' ? 'true' : '' })}>
            <option value="">Anyone</option><option value="owes">Has a balance</option><option value="over">Over their limit</option>
          </select>
        )}</Field>
        <Field label="Sort by">{(id) => (
          <select id={id} className="inp" value={f.ordering} onChange={(e) => set('ordering', e.target.value)}>
            <option value="">Name</option><option value="-outstanding">Owes most</option><option value="-created_at">Newest</option>
          </select>
        )}</Field>
      </div>
      <div className="tw">
        <QueryState query={q} empty={q.data?.results.length === 0} emptyHint="No customers match">
          <table className="tbl">
            <thead><tr><th>Name</th><th>Shop</th><th>Phone</th><th>City</th><th>Type</th><th>Credit</th><th className="r">Limit</th><th className="r">Owes</th></tr></thead>
            <tbody>
              {q.data?.results.map((c) => (
                <tr key={c.id} className={c.is_active ? undefined : 'dim'}>
                  <td><Link to={`/customers/${c.id}`} style={{ fontWeight: 600 }}>{c.name}</Link></td>
                  <td>{c.shop_name || '—'}</td>
                  <td className="mono" style={{ fontSize: 13 }}>{c.phone || '—'}</td>
                  <td>{c.city || '—'}</td>
                  <td>{label(c.type)}</td>
                  <td>{c.credit_allowed ? 'Allowed' : '—'}</td>
                  <td className="r">{c.credit_allowed ? (c.credit_limit ? money(c.credit_limit) : 'No limit') : '—'}</td>
                  <td className="r">
                    <span className="row" style={{ justifyContent: 'flex-end', gap: 8, flexWrap: 'nowrap' }}>
                      {c.over_limit && <span className="chip c-amber">Over limit</span>}
                      <strong style={{ color: Number(c.outstanding) > 0 ? undefined : 'var(--faint)' }}>{money(c.outstanding)}</strong>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </QueryState>
      </div>
      <Pager page={page} count={q.data?.count ?? 0} onPage={setPage} />
    </main>
  )
}
