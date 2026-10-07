import { Link } from 'react-router-dom'
import { useApi, useRealLocations } from '../../api/hooks'
import type { Paginated, Transfer } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { DocLink, EthDate, Field, PageHeader, Pager, QueryState, StatusChip, Tabs } from '../../components/ui'
import { useFilters } from '../../lib/useFilters'

// P-25 Transfers: Incoming · Outgoing · All (accountant / admin).
export default function Transfers() {
  const { user, is } = useAuth()
  const office = is('accountant', 'admin')
  const home = user?.home_location ?? null
  const { values: f, set, page, setPage } = useFilters(['tab', 'status', 'from_location', 'to_location'] as const, { tab: office ? 'all' : 'incoming' })
  const { data: locations } = useRealLocations()
  const params: Record<string, string | number> = { status: f.status, page }
  if (f.tab === 'incoming' && home) params.to_location = home
  else if (f.tab === 'outgoing' && home) params.from_location = home
  else {
    if (f.from_location) params.from_location = f.from_location
    if (f.to_location) params.to_location = f.to_location
  }
  const q = useApi<Paginated<Transfer>>('/transfers/', params)
  const tabs: ['incoming' | 'outgoing' | 'all', string][] = home ? [['incoming', 'Incoming'], ['outgoing', 'Outgoing']] : []
  if (office) tabs.push(['all', 'All'])

  return (
    <main className="page">
      <PageHeader title="Transfers" sub="Stock moving between locations"
        actions={office && <Link className="btn btn-pri" to="/transfers/new">New transfer</Link>} />
      {tabs.length > 1 && <Tabs value={f.tab as 'incoming'} options={tabs} onChange={(v) => set('tab', v)} />}
      <div className="filters">
        <Field label="Status">{(id) => (
          <select id={id} className="inp" value={f.status} onChange={(e) => set('status', e.target.value)}>
            <option value="">All</option><option value="in_transit">In transit</option><option value="received">Received</option>
          </select>
        )}</Field>
        {f.tab === 'all' && <>
          <Field label="From">{(id) => (
            <select id={id} className="inp" value={f.from_location} onChange={(e) => set('from_location', e.target.value)}>
              <option value="">Any</option>{locations?.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          )}</Field>
          <Field label="To">{(id) => (
            <select id={id} className="inp" value={f.to_location} onChange={(e) => set('to_location', e.target.value)}>
              <option value="">Any</option>{locations?.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          )}</Field>
        </>}
      </div>
      <div className="tw">
        <QueryState query={q} empty={q.data?.results.length === 0} emptyHint={f.tab === 'incoming' ? 'Nothing on its way to you' : 'No transfers'}>
          <table className="tbl">
            <thead><tr><th>Number</th><th>Sent</th><th>From → to</th><th>Lines</th><th>Status</th><th>Transaction</th><th>Sent by</th><th /></tr></thead>
            <tbody>
              {q.data?.results.map((t) => (
                <tr key={t.id}>
                  <td><DocLink number={t.number} to={`/transfers/${t.id}`} strong /></td>
                  <td><EthDate value={t.sent_at} /></td>
                  <td>{t.from_location_code} → {t.to_location_code}</td>
                  <td className="wrap">{t.lines.map((l) => `${l.qty_sent} × ${l.product_code}`).join(', ')}</td>
                  <td className="row" style={{ gap: 6 }}>
                    <StatusChip kind="transfer" value={t.status} />
                    {t.discrepancy_note && <span className="chip c-amber">Short</span>}
                  </td>
                  <td><DocLink number={t.transaction_number} /></td>
                  <td>{t.sent_by_name}</td>
                  <td className="r">{t.status === 'in_transit' && (office || t.to_location === home) && <Link className="btn btn-pri btn-sm" to={`/transfers/${t.id}`}>Receive</Link>}</td>
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
