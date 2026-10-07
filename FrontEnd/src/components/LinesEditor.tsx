import type { ReactNode } from 'react'
import { ProductPicker } from './pickers'
import type { PickedProduct } from './pickers'
import { QtyStepper } from './inputs'
import { CondTag } from './ui'

export interface EditorLine {
  key: string
  product: PickedProduct
  qty: number
  condition?: string
}

/**
 * Product lines for receipts, requests and transfers: pick a product, set a quantity.
 * One line per product (and condition), as the API requires.
 */
export function LinesEditor({ lines, onChange, stockAt = [], maxFor, conditions, extra, pickerLabel = 'Add a product' }: {
  lines: EditorLine[]
  onChange: (lines: EditorLine[]) => void
  /** Location codes whose available stock the picker shows. */
  stockAt?: string[]
  /** The most a line may take (e.g. what is free at the source); undefined = no limit. */
  maxFor?: (line: EditorLine) => number | undefined
  /** Allow choosing new / display / damaged per line. */
  conditions?: boolean
  extra?: (line: EditorLine) => ReactNode
  pickerLabel?: string
}) {
  const add = (product: PickedProduct) => {
    const existing = lines.find((l) => l.product.id === product.id && (l.condition ?? 'new') === 'new')
    if (existing) onChange(lines.map((l) => (l === existing ? { ...l, qty: l.qty + 1 } : l)))
    else onChange([...lines, { key: `${product.id}-${Date.now()}`, product, qty: 1, condition: 'new' }])
  }
  const update = (key: string, patch: Partial<EditorLine>) => onChange(lines.map((l) => (l.key === key ? { ...l, ...patch } : l)))
  const remove = (key: string) => onChange(lines.filter((l) => l.key !== key))

  return (
    <div className="stack">
      <div className="fld" style={{ maxWidth: 560 }}>
        <label htmlFor="lines-picker">{pickerLabel}</label>
        <ProductPicker id="lines-picker" onPick={add} stockAt={stockAt} />
      </div>
      {lines.length > 0 && (
        <div className="tw">
          <table className="tbl">
            <thead><tr><th>Product</th>{conditions && <th>Condition</th>}<th>Quantity</th>{extra && <th />}<th /></tr></thead>
            <tbody>
              {lines.map((line) => {
                const max = maxFor?.(line)
                return (
                  <tr key={line.key}>
                    <td><span className="mono" style={{ fontWeight: 600 }}>{line.product.code}</span> {line.product.name}</td>
                    {conditions && (
                      <td>
                        <select className="inp" style={{ height: 36, width: 130 }} aria-label="Condition" value={line.condition ?? 'new'} onChange={(e) => update(line.key, { condition: e.target.value })}>
                          <option value="new">New</option><option value="display">Display</option><option value="damaged">Damaged</option>
                        </select>
                      </td>
                    )}
                    <td><QtyStepper value={line.qty} min={1} max={max} onChange={(qty) => update(line.key, { qty })} label={line.product.code} /></td>
                    {extra && <td>{extra(line)}</td>}
                    <td className="r"><button type="button" className="btn btn-q btn-sm" onClick={() => remove(line.key)} aria-label={`Remove ${line.product.code}`}>Remove</button></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export function linesSummary(lines: { qty: number; product: { code: string }; condition?: string }[]): string {
  return lines.map((l) => `${l.qty} × ${l.product.code}${l.condition && l.condition !== 'new' ? ` (${l.condition})` : ''}`).join(', ')
}

export { CondTag }
