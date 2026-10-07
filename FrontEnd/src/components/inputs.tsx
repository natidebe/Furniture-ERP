import { useEffect, useState } from 'react'
import { cleanMoneyInput } from '../lib/format'
import { useDebounced } from '../lib/useFilters'

/** Digits and one decimal point, two decimals max (UI_PAGES.md section 5). */
export function MoneyInput({ id, value, onChange, placeholder, disabled }: {
  id?: string; value: string; onChange: (v: string) => void; placeholder?: string; disabled?: boolean
}) {
  return (
    <div className="row" style={{ flexWrap: 'nowrap', gap: 6 }}>
      <input id={id} className="inp num" inputMode="decimal" value={value} placeholder={placeholder ?? '0.00'} disabled={disabled}
        onChange={(e) => onChange(cleanMoneyInput(e.target.value))} style={{ textAlign: 'right' }} />
      <span className="sub">ETB</span>
    </div>
  )
}

/** − / + with a typed value; shows the maximum allowed ("of 20"). */
export function QtyStepper({ id, value, onChange, min = 0, max, big, label }: {
  id?: string; value: number; onChange: (v: number) => void; min?: number; max?: number; big?: boolean; label?: string
}) {
  const clamp = (n: number) => Math.max(min, max !== undefined ? Math.min(max, n) : n)
  const h = big ? 52 : 40
  return (
    <div className="row" style={{ flexWrap: 'nowrap', gap: 6 }}>
      <button type="button" className="btn btn-sec" style={{ height: h, width: h, padding: 0, fontSize: 18 }} aria-label={`Less${label ? ` ${label}` : ''}`}
        disabled={value <= min} onClick={() => onChange(clamp(value - 1))}>−</button>
      <input id={id} className="inp num" inputMode="numeric" style={{ height: h, width: big ? 80 : 70, textAlign: 'center', fontSize: big ? 18 : 14, fontWeight: 600 }}
        value={String(value)} aria-label={label}
        onChange={(e) => { const n = parseInt(e.target.value.replace(/\D/g, '') || '0', 10); onChange(clamp(n)) }} />
      <button type="button" className="btn btn-sec" style={{ height: h, width: h, padding: 0, fontSize: 18 }} aria-label={`More${label ? ` ${label}` : ''}`}
        disabled={max !== undefined && value >= max} onClick={() => onChange(clamp(value + 1))}>+</button>
      {max !== undefined && <span className="sub" style={{ whiteSpace: 'nowrap' }}>of {max}</span>}
    </div>
  )
}

/** A search field that reports its value once typing stops. */
export function SearchInput({ id, value, onChange, placeholder }: {
  id?: string; value: string; onChange: (v: string) => void; placeholder?: string
}) {
  const [text, setText] = useState(value)
  const debounced = useDebounced(text)
  useEffect(() => { setText(value) }, [value])
  useEffect(() => {
    if (debounced !== value) onChange(debounced)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced])
  return <input id={id} className="inp" type="search" value={text} placeholder={placeholder} onChange={(e) => setText(e.target.value)} />
}
