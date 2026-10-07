import { Link } from 'react-router-dom'
import { locationCode, useApi, useLocations } from '../../api/hooks'
import type { Paginated, User } from '../../api/types'
import { SearchInput } from '../../components/inputs'
import { EthDate, Field, PageHeader, Pager, QueryState, StatusChip } from '../../components/ui'
import { ROLE_LABEL } from '../../lib/labels'
import { useFilters } from '../../lib/useFilters'

// P-80 Users & permissions (admin). Users are deactivated, never deleted.
export default function Users() {
  const { values: f, set, page, setPage } = useFilters(['search', 'role', 'is_active'] as const, { is_active: 'true' })
  const { data: locations } = useLocations()
  const q = useApi<Paginated<User>>('/users/', { ...f, page })
  return (
    <main className="page">
      <PageHeader title="Users & permissions" sub={q.data ? `${q.data.count} users` : ' '} actions={<Link className="btn btn-pri" to="/admin/users/new">New user</Link>} />
      <div className="filters">
        <Field label="Search" className="fld-search">{(id) => <SearchInput id={id} value={f.search} onChange={(v) => set('search', v)} placeholder="Name, username or phone" />}</Field>
        <Field label="Role">{(id) => (
          <select id={id} className="inp" value={f.role} onChange={(e) => set('role', e.target.value)}>
            <option value="">All roles</option>{Object.entries(ROLE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        )}</Field>
        <Field label="Status">{(id) => (
          <select id={id} className="inp" value={f.is_active} onChange={(e) => set('is_active', e.target.value)}>
            <option value="true">Active</option><option value="false">Deactivated</option><option value="">All</option>
          </select>
        )}</Field>
      </div>
      <div className="tw">
        <QueryState query={q} empty={q.data?.results.length === 0} emptyHint="No users match">
          <table className="tbl">
            <thead><tr><th>Name</th><th>Username</th><th>Role</th><th>Works at</th><th>Telegram</th><th>Last login</th><th>Status</th></tr></thead>
            <tbody>
              {q.data?.results.map((u) => (
                <tr key={u.id}>
                  <td><Link to={`/admin/users/${u.id}`} style={{ fontWeight: 600 }}>{u.full_name || u.username}</Link></td>
                  <td className="mono" style={{ fontSize: 13 }}>{u.username}</td>
                  <td>{ROLE_LABEL[u.role ?? ''] ?? u.role}</td>
                  <td>{u.home_location ? locationCode(locations, u.home_location) : '—'}</td>
                  <td>{u.telegram_id ? <span className="chip c-green">Linked</span> : <span className="chip c-grey">Not linked</span>}</td>
                  <td>{u.last_login ? <EthDate value={u.last_login} /> : <span className="muted">Never</span>}</td>
                  <td><StatusChip kind="active" value={String(u.is_active)} /></td>
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
