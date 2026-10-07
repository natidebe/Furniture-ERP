import { describe, expect, it } from 'vitest'
import { formatBoth, monthLength, toEthiopian, toGregorian } from './ethiopian'

describe('Ethiopian calendar (same results as backend/apps/core/ethiopian.py)', () => {
  it('converts known dates', () => {
    // From the API: /calendar/?date=2026-10-07 → Meskerem 27, 2019
    expect(toEthiopian({ y: 2026, m: 10, d: 7 })).toEqual({ year: 2019, month: 1, day: 27 })
    expect(toEthiopian({ y: 2026, m: 9, d: 11 })).toEqual({ year: 2019, month: 1, day: 1 })
    // Ethiopian new year after a Gregorian leap year falls on 12 September.
    expect(toEthiopian({ y: 2023, m: 9, d: 12 })).toEqual({ year: 2016, month: 1, day: 1 })
  })

  it('round-trips every day for eight years', () => {
    let g = toGregorian({ year: 2015, month: 1, day: 1 })
    for (let i = 0; i < 365 * 8; i++) {
      const e = toEthiopian(g)
      expect(toGregorian(e)).toEqual(g)
      const next = new Date(Date.UTC(g.y, g.m - 1, g.d + 1))
      g = { y: next.getUTCFullYear(), m: next.getUTCMonth() + 1, d: next.getUTCDate() }
    }
  })

  it('has a 6-day Pagume in leap years', () => {
    expect(monthLength(2019, 13)).toBe(6)
    expect(monthLength(2018, 13)).toBe(5)
    expect(() => toGregorian({ year: 2018, month: 13, day: 6 })).toThrow()
  })

  it('formats like the API: Ethiopian first, Gregorian beside it, Addis Ababa time', () => {
    expect(formatBoth('2026-10-06T13:36:21.353224Z')).toBe('መስከረም 26, 2019 (06/10/2026) 16:36')
    expect(formatBoth('2026-10-06T13:36:21Z', false)).toBe('መስከረም 26, 2019 (06/10/2026)')
    expect(formatBoth('2026-11-05')).toBe('ጥቅምት 26, 2019 (05/11/2026)')
  })
})
