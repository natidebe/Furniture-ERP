import { useEffect, useId, useRef, useState } from 'react'
import type { ReactNode } from 'react'

interface ComboboxProps<T> {
  id?: string
  placeholder?: string
  /** Current search text → options (already fetched by the caller). */
  query: string
  onQuery: (text: string) => void
  options: T[]
  loading?: boolean
  getKey: (option: T) => string | number
  render: (option: T) => ReactNode
  onPick: (option: T) => void
  emptyText?: string
  footer?: ReactNode
  autoFocus?: boolean
}

/** A type-ahead list with keyboard support (↑ ↓ Enter Esc). */
export function Combobox<T>({ id, placeholder, query, onQuery, options, loading, getKey, render, onPick, emptyText = 'No matches', footer, autoFocus }: ComboboxProps<T>) {
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const listId = useId()
  const wrap = useRef<HTMLDivElement>(null)

  useEffect(() => { setActive(0) }, [options])
  useEffect(() => {
    const close = (e: MouseEvent) => { if (!wrap.current?.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  const pick = (option: T) => {
    onPick(option)
    setOpen(false)
  }

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); setActive((a) => Math.min(a + 1, options.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)) }
    else if (e.key === 'Enter' && open && options[active]) { e.preventDefault(); pick(options[active]) }
    else if (e.key === 'Escape') setOpen(false)
  }

  const showList = open && query.trim().length > 0
  return (
    <div ref={wrap} style={{ position: 'relative' }}>
      <input id={id} className="inp" role="combobox" aria-expanded={showList} aria-controls={listId} aria-autocomplete="list"
        autoComplete="off" placeholder={placeholder} value={query} autoFocus={autoFocus}
        onChange={(e) => { onQuery(e.target.value); setOpen(true) }} onFocus={() => setOpen(true)} onKeyDown={onKey} />
      {showList && (
        <div id={listId} role="listbox" style={{ position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0, zIndex: 30, background: '#fff', border: '1px solid var(--line)', borderRadius: 8, boxShadow: '0 10px 30px rgba(0,0,0,.12)', maxHeight: 340, overflowY: 'auto' }}>
          {loading && options.length === 0 && <div className="sub" style={{ padding: 12 }}>Searching…</div>}
          {!loading && options.length === 0 && <div className="sub" style={{ padding: 12 }}>{emptyText}</div>}
          {options.map((option, i) => (
            <div key={getKey(option)} role="option" aria-selected={i === active}
              onMouseDown={(e) => { e.preventDefault(); pick(option) }} onMouseEnter={() => setActive(i)}
              style={{ padding: '10px 12px', cursor: 'pointer', background: i === active ? 'var(--ground)' : undefined, borderBottom: '1px solid var(--line-2)' }}>
              {render(option)}
            </div>
          ))}
          {footer}
        </div>
      )}
    </div>
  )
}
