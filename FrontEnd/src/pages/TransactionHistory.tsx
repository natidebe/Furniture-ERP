import { Link, useParams } from 'react-router-dom'
import { useApi } from '../api/hooks'
import type { TransactionHistory as History } from '../api/types'
import { Card, ErrorBanner, Loading, Money, PageHeader, StatusChip } from '../components/ui'
import { money } from '../lib/format'
import { label } from '../lib/labels'

const BAD = /reject|cancel|void|revers/i
const WARN = /short|return|correct|re-issue/i

/** Turn document numbers inside an event's text into links to their history. */
function linkify(text: string) {
  const parts = text.split(/((?:SO|PS|DN|SR|SRL|TR|GR|ADJ|PAY|RET|MV|CC)-\d{4}-\d+)/g)
  return parts.map((part, i) => (i % 2 ? <Link key={i} className="mono" to={`/transactions/${part}`}>{part}</Link> : part))
}

// P-05 Transaction history — "the same delivery paper everyone tracks", opened from any
// related number (SO, DN, SR, SRL, TR, MV, PAY, RET).
export default function TransactionHistory() {
  const { number } = useParams()
  const q = useApi<History>(`/transactions/${number}/`)
  if (q.isLoading) return <main className="page"><Loading /></main>
  if (q.error || !q.data) return <main className="page"><ErrorBanner error={q.error} /></main>
  const h = q.data.header
  const isSale = h.kind === 'sale'
  return (
    <main className="page">
      <PageHeader
        crumb="Transaction history"
        title={<span className="row" style={{ gap: 12 }}><span className="mono">{h.transaction}</span>
          {h.status && <StatusChip kind={isSale ? 'fulfilment' : 'request'} value={h.status} />}
          {h.payment_status && <StatusChip kind="orderPayment" value={h.payment_status} />}</span>}
        sub={[label(h.kind), h.customer, h.salesperson, h.branch, h.receipt_type && label(h.receipt_type)].filter(Boolean).join(' · ')}
        actions={isSale && <Link className="btn btn-sec" to={`/search?q=${h.transaction}`}>Open the sale</Link>} />
      {h.replaces && <div className="alert alert-info">Replaces <Link className="mono" to={`/transactions/${h.replaces}`}>{h.replaces}</Link></div>}
      {h.total !== undefined && (
        <div className="grid-tiles">
          <div className="tile"><span className="lbl">Total</span><span className="tile-value">{money(h.total)}</span></div>
          <div className="tile"><span className="lbl">Paid</span><span className="tile-value"><Money value={h.paid ?? null} hidden={h.paid === null} /></span></div>
          <div className="tile tile-dark"><span className="lbl">Remaining</span><span className="tile-value">{money(h.remaining)}</span></div>
        </div>
      )}
      <div className="grid-cards" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(420px, 100%), 1fr))' }}>
        {h.products && h.products.length > 0 && (
          <Card title="Products">
            <div style={{ overflowX: 'auto' }}>
              <table className="tbl">
                <thead><tr><th>Product</th><th className="r">Qty</th><th className="r">Released</th>{isSale && <th className="r">Returned</th>}{isSale && <th>Source</th>}</tr></thead>
                <tbody>
                  {h.products.map((p) => (
                    <tr key={p.code}>
                      <td><span className="mono" style={{ fontWeight: 600 }}>{p.code}</span> <span className="sub">{p.name}</span></td>
                      <td className="r">{p.qty}</td><td className="r">{p.released ?? '—'}</td>
                      {isSale && <td className="r">{p.returned ?? 0}</td>}{isSale && <td>{p.source}</td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
        <Card title="Timeline">
          <ol className="timeline">
            {q.data.events.map((e, i) => (
              <li key={i} className={BAD.test(e.event) ? 'bad' : WARN.test(e.event) || /short/i.test(e.detail) ? 'warn' : undefined}>
                <div className="stack" style={{ gap: 2 }}>
                  <span><strong>{e.event.charAt(0).toUpperCase() + e.event.slice(1)}</strong> <span className="muted">by {e.by}</span></span>
                  {e.detail && <span style={{ fontSize: 13 }}>{linkify(e.detail)}</span>}
                  {e.reason && <span className="sub">“{e.reason}”</span>}
                  <span className="sub">{e.at_ec}</span>
                </div>
              </li>
            ))}
          </ol>
        </Card>
      </div>
    </main>
  )
}
