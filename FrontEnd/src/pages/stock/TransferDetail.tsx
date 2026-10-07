import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import { useAction, useApi } from '../../api/hooks'
import type { Transfer } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { ConfirmDialog } from '../../components/Dialog'
import { QtyStepper } from '../../components/inputs'
import { Banner, Card, CondTag, DocLink, ErrorBanner, EthDate, Loading, PageHeader, StatusChip } from '../../components/ui'

// P-25 Transfer detail and Receive. Staff at the destination receive once; each line defaults
// to the full quantity and is lowered if fewer arrived. Goods for a sale are then held at the
// branch for that customer.
export default function TransferDetail() {
  const { id } = useParams()
  const { user, is } = useAuth()
  const q = useApi<Transfer>(`/transfers/${id}/`)
  const [received, setReceived] = useState<Record<number, number>>({})
  const [confirm, setConfirm] = useState(false)
  const receive = useAction(() => api.post(`/transfers/${id}/receive/`, {
    lines: q.data!.lines.map((l) => ({ line_id: l.id, qty: received[l.id] ?? l.qty_sent })),
  }), { success: `${q.data?.number} received.` })

  useEffect(() => {
    if (q.data) setReceived(Object.fromEntries(q.data.lines.map((l) => [l.id, l.qty_sent])))
  }, [q.data])

  if (q.isLoading) return <main className="page"><Loading /></main>
  if (q.error || !q.data) return <main className="page"><ErrorBanner error={q.error} /></main>
  const t = q.data
  const canReceive = t.status === 'in_transit' && (is('admin', 'accountant') || user?.home_location === t.to_location)
  const short = t.lines.reduce((s, l) => s + Math.max(0, l.qty_sent - (received[l.id] ?? l.qty_sent)), 0)

  return (
    <main className="page">
      <Link to="/transfers" style={{ fontSize: 14 }}>← Transfers</Link>
      <PageHeader
        title={<span className="row" style={{ gap: 12 }}><span className="mono">{t.number}</span><StatusChip kind="transfer" value={t.status} />{t.discrepancy_note && <span className="chip c-amber">Short</span>}</span>}
        sub={`${t.from_location_code} → ${t.to_location_code}`} />
      <Card>
        <dl className="dl">
          <dt>Sent</dt><dd><EthDate value={t.sent_at} /> by {t.sent_by_name}</dd>
          <dt>Received</dt><dd>{t.received_at ? <><EthDate value={t.received_at} /> by {t.received_by_name}</> : 'Not yet'}</dd>
          <dt>Transaction</dt><dd><DocLink number={t.transaction_number} /></dd>
          {t.stock_request && <><dt>Request</dt><dd><Link to={`/stock-requests/${t.stock_request}`}>Open the stock request</Link></dd></>}
          {t.note && <><dt>Note</dt><dd>{t.note}</dd></>}
        </dl>
        {t.discrepancy_note && <Banner kind="warn"><span><strong>Short delivery.</strong> {t.discrepancy_note}</span></Banner>}
      </Card>
      <Card title={canReceive ? 'Receive' : 'Lines'}>
        <div style={{ overflowX: 'auto' }}>
          <table className="tbl">
            <thead><tr><th>Product</th><th>Condition</th><th className="r">Sent</th><th>{canReceive ? 'Arrived' : 'Received'}</th></tr></thead>
            <tbody>
              {t.lines.map((l) => (
                <tr key={l.id}>
                  <td><span className="mono" style={{ fontWeight: 600 }}>{l.product_code}</span> {l.product_name}</td>
                  <td><CondTag condition={l.condition} /></td>
                  <td className="r">{l.qty_sent}</td>
                  <td>{canReceive
                    ? <QtyStepper value={received[l.id] ?? l.qty_sent} max={l.qty_sent} onChange={(v) => setReceived({ ...received, [l.id]: v })} label={l.product_code} />
                    : <span style={{ fontWeight: 600, color: l.qty_received !== null && l.qty_received < l.qty_sent ? 'var(--amber-fg)' : undefined }}>{l.qty_received ?? '—'}</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {canReceive && (
          <>
            {short > 0 && <Banner kind="warn">{short} still in transit — the accountant will be told.</Banner>}
            <div className="row" style={{ justifyContent: 'flex-end' }}>
              <button type="button" className="btn btn-pri btn-lg" onClick={() => setConfirm(true)}>Receive</button>
            </div>
          </>
        )}
      </Card>
      {confirm && (
        <ConfirmDialog title="Receive transfer"
          message={<>Receive <span className="mono">{t.number}</span> at {t.to_location_code}: <strong>{t.lines.map((l) => `${received[l.id] ?? l.qty_sent} × ${l.product_code}`).join(', ')}</strong>?{short > 0 && <> {short} short.</>} This can be done once only.</>}
          confirmLabel="Receive" onConfirm={() => receive.mutateAsync(undefined)} onClose={() => setConfirm(false)} />
      )}
    </main>
  )
}
