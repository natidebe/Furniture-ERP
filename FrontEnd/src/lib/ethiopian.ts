// The Ethiopian calendar (D16): dates are shown Ethiopian first with the Gregorian date
// beside them. A port of backend/apps/core/ethiopian.py, so the screen and the server agree:
// twelve 30-day months, then Pagume with 5 days (6 when the Ethiopian year % 4 == 3);
// conversion goes through the Julian day number (Amete Mihret era).

export const MONTHS_AM = ['መስከረም', 'ጥቅምት', 'ኅዳር', 'ታኅሣሥ', 'ጥር', 'የካቲት', 'መጋቢት', 'ሚያዝያ',
  'ግንቦት', 'ሰኔ', 'ሐምሌ', 'ነሐሴ', 'ጳጉሜ']
export const MONTHS_EN = ['Meskerem', 'Tikimt', 'Hidar', 'Tahsas', 'Tir', 'Yekatit', 'Megabit',
  'Miyazya', 'Ginbot', 'Sene', 'Hamle', 'Nehase', 'Pagume']

export const TIME_ZONE = 'Africa/Addis_Ababa'
const EPOCH = 1723856

export interface EthDate { year: number; month: number; day: number }
/** A calendar date without a time: { y, m (1–12), d }. */
export interface GregDate { y: number; m: number; d: number }

export function isLeap(year: number): boolean {
  return year % 4 === 3
}

export function monthLength(year: number, month: number): number {
  if (month < 13) return 30
  return isLeap(year) ? 6 : 5
}

const floorDiv = (a: number, b: number) => Math.floor(a / b)
const mod = (a: number, b: number) => ((a % b) + b) % b

function gregToJdn({ y, m, d }: GregDate): number {
  const a = floorDiv(14 - m, 12)
  const yy = y + 4800 - a
  const mm = m + 12 * a - 3
  return d + floorDiv(153 * mm + 2, 5) + 365 * yy + floorDiv(yy, 4) - floorDiv(yy, 100)
    + floorDiv(yy, 400) - 32045
}

function jdnToGreg(jdn: number): GregDate {
  const a = jdn + 32044
  const b = floorDiv(4 * a + 3, 146097)
  const c = a - floorDiv(146097 * b, 4)
  const d = floorDiv(4 * c + 3, 1461)
  const e = c - floorDiv(1461 * d, 4)
  const m = floorDiv(5 * e + 2, 153)
  return {
    d: e - floorDiv(153 * m + 2, 5) + 1,
    m: m + 3 - 12 * floorDiv(m, 10),
    y: 100 * b + d - 4800 + floorDiv(m, 10),
  }
}

export function toEthiopian(g: GregDate): EthDate {
  const jdn = gregToJdn(g)
  const r = mod(jdn - EPOCH, 1461)
  const n = (r % 365) + 365 * floorDiv(r, 1460)
  const year = 4 * floorDiv(jdn - EPOCH, 1461) + floorDiv(r, 365) - floorDiv(r, 1460)
  return { year, month: floorDiv(n, 30) + 1, day: (n % 30) + 1 }
}

export function toGregorian({ year, month, day }: EthDate): GregDate {
  if (month < 1 || month > 13 || day < 1 || day > monthLength(year, month)) {
    throw new RangeError(`No such Ethiopian date: ${year}-${month}-${day}.`)
  }
  const jdn = EPOCH + 365 + 365 * (year - 1) + floorDiv(year, 4) + 30 * month + day - 31
  return jdnToGreg(jdn)
}

const pad = (n: number) => String(n).padStart(2, '0')

/** "2026-10-07" → { y, m, d }; null when the text is not an ISO date. */
export function parseIsoDate(text: string): GregDate | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(text)
  return m ? { y: +m[1], m: +m[2], d: +m[3] } : null
}

export function isoDate({ y, m, d }: GregDate): string {
  return `${y}-${pad(m)}-${pad(d)}`
}

const partsFormat = new Intl.DateTimeFormat('en-GB', {
  timeZone: TIME_ZONE, year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
})

/** The Addis Ababa calendar date and time of an instant. */
export function addisParts(when: Date): GregDate & { hh: string; mi: string } {
  const p: Record<string, string> = {}
  for (const part of partsFormat.formatToParts(when)) p[part.type] = part.value
  return { y: +p.year, m: +p.month, d: +p.day, hh: p.hour, mi: p.minute }
}

export function todayAddis(): GregDate {
  const { y, m, d } = addisParts(new Date())
  return { y, m, d }
}

export function formatEc(e: EthDate): string {
  return `${MONTHS_AM[e.month - 1]} ${e.day}, ${e.year}`
}

export function formatGreg({ y, m, d }: GregDate): string {
  return `${pad(d)}/${pad(m)}/${y}`
}

/**
 * Ethiopian first, Gregorian beside it — "ጥቅምት 26, 2019 (05/11/2026) 14:35".
 * A date-only string ("2026-11-05") is taken as that calendar day; a timestamp is shown in
 * Addis Ababa time, with the time unless `withTime` is false.
 */
export function formatBoth(value: string | Date | null | undefined, withTime = true): string {
  if (!value) return ''
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const g = parseIsoDate(value)!
    return `${formatEc(toEthiopian(g))} (${formatGreg(g)})`
  }
  const when = typeof value === 'string' ? new Date(value) : value
  if (Number.isNaN(when.getTime())) return String(value)
  const p = addisParts(when)
  const text = `${formatEc(toEthiopian(p))} (${formatGreg(p)})`
  return withTime ? `${text} ${p.hh}:${p.mi}` : text
}

/** Only the Ethiopian part: "ጥቅምት 26, 2019". */
export function formatEcOnly(value: string | Date | null | undefined): string {
  if (!value) return ''
  const g = typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)
    ? parseIsoDate(value)!
    : addisParts(typeof value === 'string' ? new Date(value) : value)
  return formatEc(toEthiopian(g))
}

export function addDays(g: GregDate, days: number): GregDate {
  return jdnToGreg(gregToJdn(g) + days)
}

export function weekdayName(g: GregDate): string {
  // JDN 0 was a Monday.
  return ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][mod(gregToJdn(g), 7)]
}
