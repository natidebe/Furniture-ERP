import { useEffect, useRef, useState } from 'react'
import {
  MONTHS_AM, MONTHS_EN, formatBoth, isoDate, monthLength, parseIsoDate, toEthiopian, toGregorian,
  todayAddis,
} from '../lib/ethiopian'

/**
 * Ethiopian date picker (D16): a month of 30 days (Pagume 5 or 6) in the Ethiopian year, with
 * the Gregorian date under each day. The value in and out is the Gregorian ISO date the API
 * takes ("2026-10-07").
 */
export function EthDatePicker({ id, value, onChange, placeholder = 'Pick a date', clearable = true }: {
  id?: string
  value: string
  onChange: (iso: string) => void
  placeholder?: string
  clearable?: boolean
}) {
  const [open, setOpen] = useState(false)
  const selected = parseIsoDate(value)
  const start = toEthiopian(selected ?? todayAddis())
  const [view, setView] = useState({ year: start.year, month: start.month })
  const wrap = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const s = toEthiopian(parseIsoDate(value) ?? todayAddis())
    setView({ year: s.year, month: s.month })
  }, [open, value])
  useEffect(() => {
    const close = (e: MouseEvent) => { if (!wrap.current?.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  const step = (delta: number) => {
    let { year, month } = view
    month += delta
    if (month < 1) { year -= 1; month = 13 }
    if (month > 13) { year += 1; month = 1 }
    setView({ year, month })
  }

  const days = Array.from({ length: monthLength(view.year, view.month) }, (_, i) => i + 1)
  const selectedEc = selected ? toEthiopian(selected) : null
  const todayEc = toEthiopian(todayAddis())

  return (
    <div ref={wrap} style={{ position: 'relative' }}>
      <div className="row" style={{ flexWrap: 'nowrap', gap: 6 }}>
        <button id={id} type="button" className="inp" style={{ textAlign: 'left', cursor: 'pointer' }} aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen(!open)}>
          {value ? formatBoth(value) : <span className="muted">{placeholder}</span>}
        </button>
        {clearable && value && <button type="button" className="btn btn-q btn-sm" onClick={() => onChange('')} aria-label="Clear date">×</button>}
      </div>
      {open && (
        <div role="dialog" aria-label="Choose a date" style={{ position: 'absolute', top: 'calc(100% + 4px)', left: 0, zIndex: 30, background: '#fff', border: '1px solid var(--line)', borderRadius: 10, boxShadow: '0 10px 30px rgba(0,0,0,.14)', padding: 14, width: 320 }}>
          <div className="spread" style={{ marginBottom: 10, flexWrap: 'nowrap' }}>
            <button type="button" className="btn btn-sec btn-sm" aria-label="Previous month" onClick={() => step(-1)}>‹</button>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontWeight: 600 }}>{MONTHS_AM[view.month - 1]} {view.year}</div>
              <div className="sub">{MONTHS_EN[view.month - 1]}</div>
            </div>
            <button type="button" className="btn btn-sec btn-sm" aria-label="Next month" onClick={() => step(1)}>›</button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 4 }}>
            {days.map((day) => {
              const g = toGregorian({ year: view.year, month: view.month, day })
              const isSel = selectedEc?.year === view.year && selectedEc.month === view.month && selectedEc.day === day
              const isToday = todayEc.year === view.year && todayEc.month === view.month && todayEc.day === day
              return (
                <button key={day} type="button" onClick={() => { onChange(isoDate(g)); setOpen(false) }}
                  aria-label={formatBoth(isoDate(g))} aria-pressed={isSel}
                  style={{ border: isToday ? '1px solid var(--primary)' : '1px solid transparent', borderRadius: 6, padding: '4px 0', cursor: 'pointer', background: isSel ? 'var(--primary)' : 'var(--surface-2)', color: isSel ? '#fff' : 'var(--ink)', lineHeight: 1.2 }}>
                  <div style={{ fontWeight: 600 }}>{day}</div>
                  <div style={{ fontSize: 10, opacity: .75 }}>{g.d}/{g.m}</div>
                </button>
              )
            })}
          </div>
          <div className="spread" style={{ marginTop: 10 }}>
            <button type="button" className="btn btn-q btn-sm" onClick={() => { onChange(isoDate(todayAddis())); setOpen(false) }}>Today</button>
            <span className="sub">Gregorian day/month under each day</span>
          </div>
        </div>
      )}
    </div>
  )
}
