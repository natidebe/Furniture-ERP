import { useState } from 'react'
import { api } from '../../api/client'
import { useAction } from '../../api/hooks'
import type { Product } from '../../api/types'
import { Dialog } from '../../components/Dialog'
import { MoneyInput } from '../../components/inputs'
import { ErrorBanner, Field } from '../../components/ui'
import { money } from '../../lib/format'

// P-13 — the only way a price changes; every change lands in the price history.
export function ChangePriceDialog({ product, initialType = 'selling', onClose }: {
  product: Product
  initialType?: 'selling' | 'wholesale'
  onClose: () => void
}) {
  const [priceType, setPriceType] = useState<'selling' | 'wholesale'>(initialType)
  const [newPrice, setNewPrice] = useState('')
  const [reason, setReason] = useState('')
  const [error, setError] = useState<unknown>(null)
  const current = priceType === 'selling' ? product.selling_price : product.wholesale_price
  const change = useAction(
    () => api.post(`/products/${product.id}/change-price/`, { price_type: priceType, new_price: newPrice, reason }),
    { success: `${product.code} ${priceType} price is now ${money(newPrice)}.`, onSuccess: onClose, toastErrors: false },
  )

  const n = Number(newPrice)
  const problem = !newPrice ? null
    : n <= 0 ? 'The new price must be greater than zero.'
      : current && n === Number(current) ? `It is already ${money(current)}.`
        : priceType === 'wholesale' && n > Number(product.selling_price) ? `Wholesale can't be above the selling price ${money(product.selling_price)}.`
          : priceType === 'selling' && product.wholesale_price && n < Number(product.wholesale_price) ? `To set the selling price below ${money(product.wholesale_price)}, lower the wholesale price first.`
            : null

  const submit = async () => {
    setError(null)
    try { await change.mutateAsync(undefined) } catch (e) { setError(e) }
  }

  return (
    <Dialog title="Change price" onClose={onClose} footer={<>
      <button type="button" className="btn btn-sec" onClick={onClose}>Cancel</button>
      <button type="button" className="btn btn-pri" disabled={!newPrice || Boolean(problem) || change.isPending} onClick={submit}>
        {newPrice ? `Change to ${money(newPrice)}` : 'Change price'}
      </button>
    </>}>
      <span className="muted"><span className="mono">{product.code}</span> {product.name}</span>
      <div className="row" role="radiogroup" aria-label="Which price" style={{ gap: 20 }}>
        <label className="check"><input type="radio" name="pt" checked={priceType === 'selling'} onChange={() => setPriceType('selling')} />Selling price</label>
        <label className="check"><input type="radio" name="pt" checked={priceType === 'wholesale'} onChange={() => setPriceType('wholesale')} />Wholesale price</label>
      </div>
      <div className="form-grid">
        <Field label="Current (ETB)">{(id) => <input id={id} className="inp num" readOnly value={current ? money(current) : 'Not set'} />}</Field>
        <Field label="New price" error={problem ?? undefined}>{(id) => <MoneyInput id={id} value={newPrice} onChange={setNewPrice} />}</Field>
      </div>
      <Field label="Reason">{(id) => <input id={id} className="inp" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Supplier price rise on the October shipment" maxLength={255} />}</Field>
      <span className="sub" style={{ fontSize: 13 }}>Sales already made keep their price.</span>
      {Boolean(error) && <ErrorBanner error={error} />}
    </Dialog>
  )
}
