import { EthDatePicker } from './EthDatePicker'
import { Field, Seg } from './ui'

export type Period = 'day' | 'week' | 'month' | 'year' | 'custom'

export interface PeriodValue {
  period: Period
  calendar: 'ethiopian' | 'gregorian'
  from: string
  to: string
}

/** The report query params for a period: ?period=&calendar= or ?from=&to=. */
export function periodParams(v: PeriodValue): Record<string, string> {
  if (v.period === 'custom') return v.from && v.to ? { from: v.from, to: v.to } : {}
  return { period: v.period, calendar: v.calendar }
}

/** Today · This week · This month · This year (Ethiopian by default, D16) · Custom range. */
export function PeriodPicker({ value, onChange }: { value: PeriodValue; onChange: (v: PeriodValue) => void }) {
  const set = (patch: Partial<PeriodValue>) => onChange({ ...value, ...patch })
  return (
    <div className="filters">
      <div className="fld" style={{ flex: '0 0 auto' }}>
        <span className="fld-label">Period</span>
        <Seg labelText="Period" value={value.period} onChange={(period) => set({ period })}
          options={[['day', 'Today'], ['week', 'This week'], ['month', 'This month'], ['year', 'This year'], ['custom', 'Custom']]} />
      </div>
      {(value.period === 'month' || value.period === 'year') && (
        <div className="fld" style={{ flex: '0 0 auto' }}>
          <span className="fld-label">Calendar</span>
          <Seg labelText="Calendar" value={value.calendar} onChange={(calendar) => set({ calendar })}
            options={[['ethiopian', 'Ethiopian'], ['gregorian', 'Gregorian']]} />
        </div>
      )}
      {value.period === 'custom' && (
        <>
          <Field label="From" style={{ flex: '0 1 260px' }}>{(id) => <EthDatePicker id={id} value={value.from} onChange={(from) => set({ from })} />}</Field>
          <Field label="To" style={{ flex: '0 1 260px' }}>{(id) => <EthDatePicker id={id} value={value.to} onChange={(to) => set({ to })} />}</Field>
        </>
      )}
    </div>
  )
}
