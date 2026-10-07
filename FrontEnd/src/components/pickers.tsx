import { useState } from 'react'
import { useApi } from '../api/hooks'
import type { Customer, Paginated, Product, StockRow, StockSummary } from '../api/types'
import { money } from '../lib/format'
import { label } from '../lib/labels'
import { useDebounced } from '../lib/useFilters'
import { Combobox } from './Combobox'

export interface PickedProduct extends Product {
  stock: StockRow['stock']
  total_new: number
}

/** Price this customer pays: resellers get the wholesale price when one is set (D11). */
export function priceFor(product: Pick<Product, 'selling_price' | 'wholesale_price'>, customerType?: string) {
  if (customerType === 'reseller' && product.wholesale_price) return { price: product.wholesale_price, wholesale: true }
  return { price: product.selling_price, wholesale: false }
}

/**
 * Product picker: type a code or name → code, name, price for the customer and stock at the
 * locations that matter (UI_PAGES.md section 5). Two calls: products (prices) and the stock
 * summary (stock), merged by product.
 */
export function ProductPicker({ id, onPick, customerType, stockAt = [], placeholder, autoFocus }: {
  id?: string
  onPick: (p: PickedProduct) => void
  customerType?: string
  /** Location codes whose available stock is shown in each suggestion. */
  stockAt?: string[]
  placeholder?: string
  autoFocus?: boolean
}) {
  const [text, setText] = useState('')
  const q = useDebounced(text.trim(), 250)
  const products = useApi<Paginated<Product>>(q ? '/products/' : null, { search: q, is_active: true })
  const stock = useApi<StockSummary>(q ? '/stock/summary/' : null, { search: q })
  const rows = new Map(stock.data?.results.map((r) => [r.product, r]))
  // Show results only for what is typed now, never the previous search's (a stale pick).
  const fresh = q === text.trim() && !products.isPlaceholderData && Boolean(stock.data) && !stock.isPlaceholderData
  const options: PickedProduct[] = (fresh ? products.data?.results ?? [] : []).map((p) => ({
    ...p,
    stock: rows.get(p.id)?.stock ?? {},
    total_new: rows.get(p.id)?.total_new ?? 0,
  }))
  return (
    <Combobox id={id} placeholder={placeholder ?? 'Type a product code or name…'} autoFocus={autoFocus}
      query={text} onQuery={setText} options={options} loading={!fresh || products.isFetching}
      getKey={(p) => p.id}
      onPick={(p) => { onPick(p); setText('') }}
      render={(p) => {
        const { price, wholesale } = priceFor(p, customerType)
        return (
          <div className="spread" style={{ alignItems: 'flex-start', flexWrap: 'nowrap' }}>
            <div className="grow">
              <div><span className="mono" style={{ fontWeight: 600 }}>{p.code}</span> {p.name}</div>
              <div className="sub">
                {stockAt.map((code) => `${code} ${p.stock[code]?.available ?? 0}`).join(' · ')}
                {stockAt.length > 0 && ' · '}total {p.total_new}
              </div>
            </div>
            <div className="r num" style={{ whiteSpace: 'nowrap' }}>
              <div style={{ fontWeight: 600 }}>{money(price)}</div>
              {wholesale && <span className="tag t-blue">Wholesale</span>}
            </div>
          </div>
        )
      }}
    />
  )
}

/** Customer picker: name / phone / shop, a one-click Walk-in, and + New customer. */
export function CustomerPicker({ id, onPick, onNew, autoFocus }: {
  id?: string
  onPick: (c: Customer) => void
  onNew?: () => void
  autoFocus?: boolean
}) {
  const [text, setText] = useState('')
  const q = useDebounced(text.trim(), 250)
  const customers = useApi<Paginated<Customer>>(q ? '/customers/' : null, { search: q, is_active: true })
  const fresh = q === text.trim() && !customers.isPlaceholderData
  return (
    <Combobox id={id} placeholder="Name, phone or shop…" autoFocus={autoFocus}
      query={text} onQuery={setText} options={fresh ? customers.data?.results ?? [] : []} loading={!fresh || customers.isFetching}
      getKey={(c) => c.id} onPick={(c) => { onPick(c); setText('') }}
      emptyText="No customer found"
      footer={onNew && (
        <button type="button" className="btn btn-q" style={{ width: '100%', justifyContent: 'flex-start', height: 40 }}
          onMouseDown={(e) => { e.preventDefault(); onNew() }}>+ New customer</button>
      )}
      render={(c) => (
        <div className="spread" style={{ flexWrap: 'nowrap' }}>
          <div className="grow">
            <div style={{ fontWeight: 600 }}>{c.name}{c.shop_name && <span className="muted" style={{ fontWeight: 400 }}> · {c.shop_name}</span>}</div>
            <div className="sub">{[c.phone, c.city, label(c.type)].filter(Boolean).join(' · ')}</div>
          </div>
          {Number(c.outstanding) > 0 && <span className="sub num" style={{ whiteSpace: 'nowrap' }}>owes {money(c.outstanding)}</span>}
        </div>
      )}
    />
  )
}

/** The shared "Walk-in Customer" (one record for anonymous cash sales). */
export function useWalkInCustomer() {
  const q = useApi<Paginated<Customer>>('/customers/', { search: 'Walk-in Customer', type: 'walk_in' })
  return q.data?.results.find((c) => c.name === 'Walk-in Customer') ?? q.data?.results[0]
}
