import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import { useAction, useApi } from '../../api/hooks'
import type { Movement, Paginated, PriceHistory, Product, ProductStock } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { ConfirmDialog } from '../../components/Dialog'
import { Card, CondTag, DocLink, Empty, ErrorBanner, EthDate, Loading, PageHeader, StatusChip } from '../../components/ui'
import { money } from '../../lib/format'
import { label } from '../../lib/labels'
import { ChangePriceDialog } from './ChangePriceDialog'

// P-11 Product detail: prices, stock card per location, price history, recent movements.
export default function ProductDetail() {
  const { id } = useParams()
  const { is } = useAuth()
  const product = useApi<Product>(`/products/${id}/`)
  const stock = useApi<ProductStock>(`/products/${id}/stock/`)
  const history = useApi<PriceHistory[]>(`/products/${id}/price-history/`)
  const stockStaff = is('storekeeper', 'accountant', 'admin')
  const movements = useApi<Paginated<Movement>>(stockStaff ? '/stock/movements/' : null, { product: id, page_size: 10 })
  const [dialog, setDialog] = useState<'price' | 'deactivate' | null>(null)
  const toggle = useAction(
    () => api.patch(`/products/${id}/`, { is_active: !product.data?.is_active }),
    { success: product.data?.is_active ? 'Product deactivated.' : 'Product reactivated.' },
  )

  if (product.isLoading) return <main className="page"><Loading /></main>
  if (product.error || !product.data) return <main className="page"><ErrorBanner error={product.error} /></main>
  const p = product.data
  const s = stock.data
  const total = s && Object.values(s.stock).reduce((acc, c) => ({
    on_hand: acc.on_hand + c.on_hand, reserved: acc.reserved + c.reserved, display: acc.display + c.display,
    damaged: acc.damaged + c.damaged, available: acc.available + c.available,
  }), { on_hand: 0, reserved: 0, display: 0, damaged: 0, available: 0 })

  return (
    <main className="page">
      <Link to="/products" style={{ fontSize: 14 }}>← Products</Link>
      <PageHeader
        title={<span className="row" style={{ gap: 12 }}><span><span className="mono">{p.code}</span> {p.name}</span><StatusChip kind="active" value={String(p.is_active)} /></span>}
        sub={`${p.category_name} · ${p.unit_symbol} · minimum stock ${p.min_stock}`}
        actions={is('admin') && <>
          <button type="button" className={p.is_active ? 'btn btn-dan' : 'btn btn-sec'} onClick={() => setDialog('deactivate')}>{p.is_active ? 'Deactivate…' : 'Reactivate'}</button>
          <button type="button" className="btn btn-sec" onClick={() => setDialog('price')}>Change price</button>
          <Link className="btn btn-pri" to={`/products/${p.id}/edit`}>Edit</Link>
        </>} />
      <div className="grid-cards" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(360px, 100%), 1fr))' }}>
        <Card>
          <div className="row" style={{ gap: 40 }}>
            <div className="stack" style={{ gap: 2 }}><span className="lbl">Selling price</span><span style={{ fontSize: 26, fontWeight: 600 }} className="num">{money(p.selling_price)}</span><span className="sub">ETB</span></div>
            <div className="stack" style={{ gap: 2 }}><span className="lbl">Wholesale</span><span style={{ fontSize: 26, fontWeight: 600 }} className="num">{money(p.wholesale_price)}</span><span className="sub">{p.wholesale_price ? 'ETB · resellers' : 'Resellers pay the selling price'}</span></div>
          </div>
          {p.description && <div className="stack" style={{ gap: 4 }}><span className="lbl">Description</span><span>{p.description}</span></div>}
        </Card>
        <Card title="Stock" actions={s && <span className={s.low_stock ? 'chip c-amber' : 'sub'}>{s.low_stock ? `Low: sellable ${s.total_new} < minimum ${p.min_stock}` : `Sellable ${s.total_new} ≥ minimum ${p.min_stock}`}</span>}>
          {!s ? <Loading /> : (
            <div style={{ overflowX: 'auto' }}>
              <table className="tbl">
                <thead><tr><th>Location</th><th className="r">On hand</th><th className="r">Reserved</th><th className="r">Display</th><th className="r">Damaged</th><th className="r">Available</th></tr></thead>
                <tbody>
                  {s.locations.map((l) => {
                    const c = s.stock[l.code] ?? { on_hand: 0, reserved: 0, display: 0, damaged: 0, available: 0 }
                    return (
                      <tr key={l.code} className={c.on_hand === 0 ? 'dim' : undefined}>
                        <td>{l.code === 'TRANSIT' ? 'In transit' : l.name}</td>
                        <td className="r">{c.on_hand}</td><td className="r">{c.reserved}</td><td className="r">{c.display}</td><td className="r">{c.damaged}</td><td className="r" style={{ fontWeight: 600 }}>{c.available}</td>
                      </tr>
                    )
                  })}
                </tbody>
                {total && (
                  <tfoot>
                    <tr><td>Total <span className="sub">incl. in transit</span></td><td className="r">{s.total}</td><td className="r">{total.reserved}</td><td className="r">{total.display}</td><td className="r">{total.damaged}</td><td className="r">{total.available}</td></tr>
                    <tr><td>Sellable <span className="sub">without display / damaged</span></td><td className="r">{s.total_new}</td><td colSpan={4} /></tr>
                  </tfoot>
                )}
              </table>
            </div>
          )}
        </Card>
      </div>
      <Card title="Price history">
        {history.data?.length === 0 ? <Empty title="No price changes yet" /> : (
          <div style={{ overflowX: 'auto' }}>
            <table className="tbl">
              <thead><tr><th>Date</th><th>Price</th><th className="r">Old</th><th className="r">New</th><th>Who</th><th>Reason</th></tr></thead>
              <tbody>
                {history.data?.map((h) => (
                  <tr key={h.id}>
                    <td><EthDate value={h.changed_at} /></td>
                    <td>{label(h.price_type ?? 'selling')}</td>
                    <td className="r">{money(h.old_price)}</td>
                    <td className="r" style={{ fontWeight: 600 }}>{money(h.new_price)}</td>
                    <td>{h.changed_by_name ?? '—'}</td>
                    <td className="wrap">{h.reason || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      {stockStaff && (
        <Card title="Recent movements" actions={<Link to={`/movements?product=${p.id}`} style={{ fontSize: 13 }}>All movements</Link>}>
          {movements.data?.results.length === 0 ? <Empty title="No movements yet" /> : (
            <div style={{ overflowX: 'auto' }}>
              <table className="tbl">
                <thead><tr><th>Date</th><th>Type</th><th>Condition</th><th className="r">Qty</th><th>From → to</th><th>Transaction</th></tr></thead>
                <tbody>
                  {movements.data?.results.map((m) => (
                    <tr key={m.id}>
                      <td><EthDate value={m.occurred_at} /></td>
                      <td>{label(m.type)}</td>
                      <td><CondTag condition={m.condition ?? 'new'} /></td>
                      <td className="r" style={{ fontWeight: 600 }}>{m.qty}</td>
                      <td>{m.from_location_code ?? '—'} → {m.to_location_code ?? '—'}</td>
                      <td><DocLink number={m.transaction_number} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
      {dialog === 'price' && <ChangePriceDialog product={p} onClose={() => setDialog(null)} />}
      {dialog === 'deactivate' && (
        <ConfirmDialog title={p.is_active ? 'Deactivate product' : 'Reactivate product'} danger={p.is_active}
          message={p.is_active ? <>Deactivate <span className="mono">{p.code}</span>? It can no longer be sold or requested. Its history and stock stay.</> : <>Reactivate <span className="mono">{p.code}</span> so it can be sold again?</>}
          confirmLabel={p.is_active ? 'Deactivate' : 'Reactivate'} onConfirm={() => toggle.mutateAsync(undefined)} onClose={() => setDialog(null)} />
      )}
    </main>
  )
}
