import { useApi } from '../../api/hooks'
import type { AuditLog as Entry, Paginated, User } from '../../api/types'
import { EthDatePicker } from '../../components/EthDatePicker'
import { SearchInput } from '../../components/inputs'
import { EthDate, Field, PageHeader, Pager, QueryState } from '../../components/ui'
import { label } from '../../lib/labels'
import { useFilters } from '../../lib/useFilters'
import { useAuth } from '../../auth/AuthContext'

const MODELS: [string, string][] = [
  ['catalog.Product', 'Product'], ['sales.SalesOrder', 'Sale'], ['payments.Payment', 'Payment'],
  ['inventory.StockAdjustment', 'Stock adjustment'], ['inventory.StockMovement', 'Stock movement'],
  ['customers.Customer', 'Customer'], ['accounts.User', 'User'], ['locations.Location', 'Location'],
  ['payments.PaymentAccount', 'Payment account'], ['core.SystemSettings', 'Settings'],
]

function show(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

/** "price: 3800.00 → 4100.00" for each key that changed. */
function Changes({ before, after }: { before: unknown; after: unknown }) {
  const b = (before && typeof before === 'object' ? before : {}) as Record<string, unknown>
  const a = (after && typeof after === 'object' ? after : {}) as Record<string, unknown>
  const keys = [...new Set([...Object.keys(b), ...Object.keys(a)])]
  if (!keys.length) return <span className="muted">—</span>
  return (
    <div className="stack" style={{ gap: 2 }}>
      {keys.map((k) => (
        <span key={k} style={{ fontSize: 13 }}>
          <span className="muted">{k.replace(/_/g, ' ')}:</span> {k in b && <><span className="mono">{show(b[k])}</span> → </>}<span className="mono" style={{ fontWeight: 600 }}>{show(a[k])}</span>
        </span>
      ))}
    </div>
  )
}

// P-83 Audit log — who changed what, and when. Read-only.
export default function AuditLog() {
  const { is } = useAuth()
  const { values: f, set, page, setPage } = useFilters(['model', 'object_id', 'actor', 'action', 'source', 'from', 'to'] as const)
  const users = useApi<Paginated<User>>(is('admin') ? '/users/' : null, { page_size: 200 })
  const q = useApi<Paginated<Entry>>('/audit/', { ...f, page })
  return (
    <main className="page">
      <PageHeader title="Audit log" sub="Every important change: who, what, before → after, why" />
      <div className="filters">
        <Field label="Object">{(id) => (
          <select id={id} className="inp" value={f.model} onChange={(e) => set('model', e.target.value)}>
            <option value="">Everything</option>{MODELS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
          </select>
        )}</Field>
        <Field label="Object id">{(id) => <SearchInput id={id} value={f.object_id} onChange={(v) => set('object_id', v)} />}</Field>
        <Field label="Action">{(id) => <SearchInput id={id} value={f.action} onChange={(v) => set('action', v)} placeholder="e.g. price_change" />}</Field>
        {is('admin') && (
          <Field label="Person">{(id) => (
            <select id={id} className="inp" value={f.actor} onChange={(e) => set('actor', e.target.value)}>
              <option value="">Anyone</option>{users.data?.results.map((u) => <option key={u.id} value={u.id}>{u.full_name || u.username}</option>)}
            </select>
          )}</Field>
        )}
        <Field label="Source">{(id) => (
          <select id={id} className="inp" value={f.source} onChange={(e) => set('source', e.target.value)}>
            <option value="">Any</option><option value="web">Web</option><option value="bot">Telegram bot</option><option value="system">System</option>
          </select>
        )}</Field>
        <Field label="From" style={{ flex: '0 1 240px' }}>{(id) => <EthDatePicker id={id} value={f.from} onChange={(v) => set('from', v)} />}</Field>
        <Field label="To" style={{ flex: '0 1 240px' }}>{(id) => <EthDatePicker id={id} value={f.to} onChange={(v) => set('to', v)} />}</Field>
      </div>
      <div className="tw">
        <QueryState query={q} empty={q.data?.results.length === 0} emptyHint="No changes match">
          <table className="tbl">
            <thead><tr><th>When</th><th>Who</th><th>Action</th><th>Object</th><th>Before → after</th><th>Reason</th><th>Source</th><th>IP</th></tr></thead>
            <tbody>
              {q.data?.results.map((e) => (
                <tr key={e.id}>
                  <td><EthDate value={e.at} /></td>
                  <td>{e.actor_name || 'System'}</td>
                  <td>{label(e.action)}</td>
                  <td>{MODELS.find(([m]) => m === e.model)?.[1] ?? e.model} <span className="mono sub">#{e.object_id}</span></td>
                  <td className="wrap"><Changes before={e.before} after={e.after} /></td>
                  <td className="wrap">{e.reason || '—'}</td>
                  <td>{label(e.source)}</td>
                  <td className="mono sub">{e.ip ?? '—'}</td>
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
