// Money arrives from the API as strings ("100000.00"). The screen only formats it: no money
// arithmetic in the browser (UI_PAGES.md 3.3), except to preview a total the server will
// recompute.

const moneyFormat = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2, maximumFractionDigits: 2,
})

/** "100000.00" → "100,000.00"; null/undefined → "—". */
export function money(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  const n = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(n) ? moneyFormat.format(n) : String(value)
}

export function qty(n: number | null | undefined, unit?: string): string {
  if (n === null || n === undefined) return '—'
  return unit ? `${n} ${unit}` : String(n)
}

/** Cents as an integer, for previews only (sums of line totals before the server confirms). */
export function toCents(value: string | number | null | undefined): number {
  if (value === null || value === undefined || value === '') return 0
  return Math.round(Number(value) * 100)
}

export function fromCents(cents: number): string {
  return (cents / 100).toFixed(2)
}

/** A typed money value: digits and one decimal point, two decimals at most. */
export function cleanMoneyInput(text: string): string {
  let out = text.replace(/[^\d.]/g, '')
  const dot = out.indexOf('.')
  if (dot >= 0) out = out.slice(0, dot + 1) + out.slice(dot + 1).replace(/\./g, '').slice(0, 2)
  return out
}

export function initials(name: string): string {
  const words = name.replace(/\([^)]*\)/g, ' ').split(/[^\p{L}]+/u).filter(Boolean)
  return (words.length > 1 ? words[0][0] + words[1][0] : (words[0] ?? '?').slice(0, 2)).toUpperCase()
}

export function titleCase(text: string): string {
  const s = text.replace(/_/g, ' ')
  return s.charAt(0).toUpperCase() + s.slice(1)
}

export function pct(part: number, whole: number): number {
  return whole > 0 ? Math.round((part / whole) * 100) : 0
}
