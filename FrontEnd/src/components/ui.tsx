import { useId } from 'react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { errorMessage } from '../api/client'
import { formatBoth } from '../lib/ethiopian'
import { money } from '../lib/format'
import { chipColour, label } from '../lib/labels'
import type { ChipKind } from '../lib/labels'

export function StatusChip({ kind, value, text }: { kind: ChipKind; value: string; text?: string }) {
  return <span className={`chip c-${chipColour(kind, value)}`}>{text ?? label(value)}</span>
}

export function Chip({ colour, children }: { colour: 'grey' | 'blue' | 'green' | 'amber' | 'red'; children: ReactNode }) {
  return <span className={`chip c-${colour}`}>{children}</span>
}

/** Organization / Personal — always visible on a payment row (D3). */
export function KindBadge({ kind, short }: { kind: string | null | undefined; short?: boolean }) {
  if (!kind) return null
  const personal = kind === 'personal'
  return <span className={personal ? 'kind k-per' : 'kind k-org'}>{personal ? 'Personal' : short ? 'Org' : 'Organization'}</span>
}

export function CondTag({ condition }: { condition: string }) {
  if (!condition || condition === 'new') return <span className="tag t-new">New</span>
  return <span className="tag t-cond">{label(condition)}</span>
}

const PREFIX_ROUTES: [RegExp, (n: string) => string][] = [
  [/^(SO|PS)-/, (n) => `/transactions/${n}`],
  [/^SR-/, (n) => `/transactions/${n}`],
]

/**
 * A document number: monospace, always a link (UI_PAGES.md 3.4). With `to`, it opens that
 * page; without, the transaction history for the number.
 */
export function DocLink({ number, to, strong }: { number: string | null | undefined; to?: string; strong?: boolean }) {
  if (!number) return <span className="muted">—</span>
  const target = to ?? PREFIX_ROUTES.find(([re]) => re.test(number))?.[1](number) ?? `/transactions/${number}`
  return <Link className="mono" to={target} style={{ fontSize: 13, fontWeight: strong ? 600 : undefined }}>{number}</Link>
}

/** Money as the API sends it; `hidden` when a Personal amount may not be seen. */
export function Money({ value, hidden, unit, strong }: { value: string | number | null | undefined; hidden?: boolean; unit?: boolean; strong?: boolean }) {
  if (hidden) return <span className="muted" title="Personal-account amounts need view_personal_payments">— hidden</span>
  return (
    <span className="num" style={{ fontWeight: strong ? 600 : undefined }}>
      {money(value)}{unit && value !== null && value !== undefined && <span className="sub"> ETB</span>}
    </span>
  )
}

/** "ጥቅምት 26, 2019 (05/11/2026) 14:35" — Ethiopian first. Prefer the API's ready-made *_ec. */
export function EthDate({ value, ec, time = true }: { value?: string | null; ec?: string | null; time?: boolean }) {
  const text = ec || formatBoth(value ?? null, time)
  if (!text) return <span className="muted">—</span>
  const split = /^(.*?) (\(.*)$/.exec(text)
  if (!split) return <span>{text}</span>
  return <span style={{ whiteSpace: 'nowrap' }}>{split[1]} <span className="sub">{split[2]}</span></span>
}

export function PageHeader({ title, sub, actions, crumb }: { title: ReactNode; sub?: ReactNode; actions?: ReactNode; crumb?: ReactNode }) {
  return (
    <div className="page-head">
      <div className="titles">
        {crumb && <span className="crumb">{crumb}</span>}
        {sub && <span className="sub" style={{ fontSize: 13 }}>{sub}</span>}
        <h1>{title}</h1>
      </div>
      {actions && <div className="actions">{actions}</div>}
    </div>
  )
}

export function ErrorBanner({ text, error }: { text?: string; error?: unknown }) {
  const message = text ?? errorMessage(error)
  return <div className="alert alert-err" role="alert"><strong>!</strong><span>{message}</span></div>
}

export function Banner({ kind, children }: { kind: 'warn' | 'ok' | 'info' | 'err'; children: ReactNode }) {
  return <div className={`alert alert-${kind}`} role={kind === 'err' ? 'alert' : 'status'}>{children}</div>
}

export function Empty({ title, hint }: { title: string; hint?: string }) {
  return <div className="empty"><strong>{title}</strong>{hint && <span style={{ fontSize: 13 }}>{hint}</span>}</div>
}

export function Loading({ text = 'Loading…' }: { text?: string }) {
  return <div className="loading" role="status">{text}</div>
}

/** Loading / error / empty states for any list or detail query. */
export function QueryState({ query, empty, emptyHint, children }: {
  query: { isLoading: boolean; isError: boolean; error: unknown; data?: unknown }
  empty?: boolean
  emptyHint?: string
  children: ReactNode
}) {
  if (query.isLoading) return <Loading />
  if (query.isError) return <div style={{ padding: 16 }}><ErrorBanner error={query.error} /></div>
  if (empty) return <Empty title={emptyHint ?? 'Nothing here yet'} />
  return <>{children}</>
}

interface FieldProps {
  label: string
  children: (id: string) => ReactNode
  hint?: ReactNode
  error?: string[] | string
  className?: string
  style?: React.CSSProperties
}

export function Field({ label: text, children, hint, error, className, style }: FieldProps) {
  const id = useId()
  const errors = typeof error === 'string' ? [error] : error
  return (
    <div className={className ? `fld ${className}` : 'fld'} style={style}>
      <label htmlFor={id}>{text}</label>
      {children(id)}
      {hint && <span className="fld-hint">{hint}</span>}
      {errors?.map((e) => <span key={e} className="fld-err">{e}</span>)}
    </div>
  )
}

export function Pager({ page, count, pageSize = 25, onPage, note }: { page: number; count: number; pageSize?: number; onPage: (p: number) => void; note?: ReactNode }) {
  const pages = Math.max(1, Math.ceil(count / pageSize))
  const first = count === 0 ? 0 : (page - 1) * pageSize + 1
  const last = Math.min(count, page * pageSize)
  return (
    <div className="pager">
      <span>{note}</span>
      <div className="row">
        <span>{first}–{last} of {count}</span>
        <button className="btn btn-sec btn-sm" type="button" aria-label="Previous page" disabled={page <= 1} onClick={() => onPage(page - 1)}>‹</button>
        <button className="btn btn-sec btn-sm" type="button" aria-label="Next page" disabled={page >= pages} onClick={() => onPage(page + 1)}>›</button>
      </div>
    </div>
  )
}

export function Tabs<T extends string>({ value, options, onChange }: { value: T; options: [T, string][]; onChange: (v: T) => void }) {
  return (
    <div className="tabs" role="tablist">
      {options.map(([key, text]) => (
        <button key={key} type="button" role="tab" aria-selected={value === key} onClick={() => onChange(key)}>{text}</button>
      ))}
    </div>
  )
}

export function Seg<T extends string>({ value, options, onChange, labelText }: { value: T; options: [T, string][]; onChange: (v: T) => void; labelText: string }) {
  return (
    <div className="seg" role="group" aria-label={labelText}>
      {options.map(([key, text]) => (
        <button key={key} type="button" aria-pressed={value === key} onClick={() => onChange(key)}>{text}</button>
      ))}
    </div>
  )
}

export function Card({ title, actions, children, style }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; style?: React.CSSProperties }) {
  return (
    <section className="card card-pad" style={style}>
      {(title || actions) && <div className="spread"><h2>{title}</h2>{actions}</div>}
      {children}
    </section>
  )
}
