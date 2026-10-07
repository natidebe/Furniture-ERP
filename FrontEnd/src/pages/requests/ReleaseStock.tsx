import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import { useAction, useApi } from '../../api/hooks'
import type { RequestRelease, StockRequest } from '../../api/types'
import { QtyStepper } from '../../components/inputs'
import { ErrorBanner, Loading } from '../../components/ui'

type Step = 'edit' | 'confirm' | 'done'

// P-33 Release stock — phone first: releases happen on the warehouse floor.
// 1. quantity taken out per open line (0 skips it) · 2. destination · 3. note · 4. confirm.
export default function ReleaseStock() {
  const { id } = useParams()
  const q = useApi<StockRequest>(`/stock-requests/${id}/`)
  const [qty, setQty] = useState<Record<number, number>>({})
  const [destination, setDestination] = useState<'branch' | 'customer_pickup'>('branch')
  const [note, setNote] = useState('')
  const [step, setStep] = useState<Step>('edit')
  const [result, setResult] = useState<RequestRelease | null>(null)
  const [error, setError] = useState<unknown>(null)
  const release = useAction(() => api.post<RequestRelease>(`/stock-requests/${id}/release/`, {
    destination_type: destination, note,
    lines: Object.entries(qty).filter(([, n]) => n > 0).map(([lineId, n]) => ({ line_id: Number(lineId), qty: n })),
  }), { onSuccess: (r) => { setResult(r as RequestRelease); setStep('done') }, toastErrors: false })

  useEffect(() => {
    if (q.data && !Object.keys(qty).length) {
      setQty(Object.fromEntries(q.data.lines.filter((l) => l.qty_remaining > 0).map((l) => [l.id, l.qty_remaining])))
    }
  }, [q.data, qty])

  if (q.isLoading) return <main className="page"><Loading /></main>
  if (q.error || !q.data) return <main className="page"><ErrorBanner error={q.error} /></main>
  const r = q.data
  const open = r.lines.filter((l) => l.qty_remaining > 0)
  const chosen = open.filter((l) => (qty[l.id] ?? 0) > 0)
  const summary = chosen.map((l) => `${qty[l.id]} × ${l.product_code}`).join(', ')
  const canRelease = r.status === 'acknowledged' || r.status === 'partially_released'

  const confirm = async () => {
    setError(null)
    try { await release.mutateAsync(undefined) } catch (e) { setError(e); setStep('edit') }
  }

  return (
    <main className="page" style={{ maxWidth: 560, margin: '0 auto', width: '100%', paddingBottom: 120 }}>
      <header className="stack" style={{ gap: 4 }}>
        <Link to={`/stock-requests/${r.id}`} className="mono">← {r.number}</Link>
        <h1>Release stock</h1>
        <span className="muted">{[r.requesting_location_code, r.customer_name, r.salesperson_name].filter(Boolean).join(' · ')}</span>
      </header>

      {!canRelease && step !== 'done' && <ErrorBanner text={r.status === 'pending' ? 'Acknowledge the request before releasing.' : `This request is ${r.status.replace('_', ' ')}: nothing to release.`} />}
      {Boolean(error) && <ErrorBanner error={error} />}

      {step === 'edit' && canRelease && (
        <>
          {open.map((l) => (
            <section key={l.id} className="card" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div className="spread"><span className="mono" style={{ fontWeight: 700, fontSize: 18 }}>{l.product_code}</span><span className="sub">{l.qty_remaining} remaining</span></div>
              <span className="muted">{l.product_name}</span>
              <div className="row" style={{ flexWrap: 'nowrap' }}>
                <QtyStepper big value={qty[l.id] ?? 0} max={l.qty_remaining} onChange={(n) => setQty({ ...qty, [l.id]: n })} label={l.product_code} />
                <button type="button" className="btn btn-sec" style={{ height: 52 }} onClick={() => setQty({ ...qty, [l.id]: l.qty_remaining })}>All</button>
              </div>
              {(qty[l.id] ?? 0) === 0 && <span className="sub">0 — this line is skipped.</span>}
            </section>
          ))}
          <fieldset className="card" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 10, margin: 0 }}>
            <legend className="lbl" style={{ padding: '0 4px' }}>Destination</legend>
            {([['branch', 'To branch', `Goods go to ${r.requesting_location_code}; they must receive them`], ['customer_pickup', 'Customer pickup', r.customer ? `${r.customer_name} collects here at ${r.source_location_code}` : 'Only when the request names a customer']] as const).map(([value, title, hint]) => {
              const disabled = value === 'customer_pickup' && !r.customer
              return (
                <button key={value} type="button" disabled={disabled} aria-pressed={destination === value} onClick={() => setDestination(value)}
                  style={{ textAlign: 'left', padding: 14, borderRadius: 8, cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.5 : 1, border: destination === value ? '2px solid var(--primary)' : '1px solid var(--field)', background: destination === value ? 'var(--primary-soft)' : '#fff', display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <span style={{ fontWeight: 600, fontSize: 16 }}>{title}</span><span className="sub">{hint}</span>
                </button>
              )
            })}
          </fieldset>
          <div className="fld">
            <label htmlFor="note">Note (optional)</label>
            <input id="note" className="inp" style={{ height: 48 }} value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. loaded on Isuzu 3-12345" />
          </div>
        </>
      )}

      {step === 'confirm' && (
        <section className="card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <span className="lbl">Confirm</span>
          <span style={{ fontSize: 18, fontWeight: 600 }}>
            Release {summary} {destination === 'branch' ? `to ${r.requesting_location_code}` : `to ${r.customer_name} (pickup)`}?
          </span>
          <span className="muted">Stock leaves {r.source_location_code} as soon as you confirm.</span>
        </section>
      )}

      {step === 'done' && result && (
        <section className="card" style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 14, alignItems: 'center', textAlign: 'center' }}>
          <span style={{ width: 52, height: 52, borderRadius: 26, background: 'var(--green-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#1B6B3A" strokeWidth="2.5" aria-hidden="true"><path d="M5 12l5 5 9-10" /></svg>
          </span>
          <span style={{ fontSize: 22, fontWeight: 600 }}>Released</span>
          <div className="stack" style={{ gap: 6, width: '100%' }}>
            <div className="spread"><span className="muted">Release</span><span className="mono" style={{ fontWeight: 600 }}>{result.number}</span></div>
            {result.transfer_number && <div className="spread"><span className="muted">Transfer to {r.requesting_location_code}</span><span className="mono" style={{ fontWeight: 600 }}>{result.transfer_number}</span></div>}
          </div>
          <Link className="btn btn-pri btn-lg btn-block" to="/stock-requests">Back to requests</Link>
          <Link to={`/stock-requests/${r.id}`}>Open the request</Link>
        </section>
      )}

      {step !== 'done' && canRelease && (
        <div style={{ position: 'fixed', left: 0, right: 0, bottom: 0, background: '#fff', borderTop: '1px solid var(--line)', padding: '12px 16px', display: 'flex', gap: 10, alignItems: 'center', justifyContent: 'center', zIndex: 25 }}>
          <div style={{ maxWidth: 528, width: '100%', display: 'flex', gap: 10, alignItems: 'center' }}>
            {step === 'edit' ? (
              <>
                <span className="grow sub" style={{ fontSize: 13 }}>{summary || 'Nothing chosen'}</span>
                <button type="button" className="btn btn-pri btn-lg" disabled={!chosen.length} onClick={() => setStep('confirm')}>Review release</button>
              </>
            ) : (
              <>
                <button type="button" className="btn btn-sec btn-lg" onClick={() => setStep('edit')}>Back</button>
                <button type="button" className="btn btn-pri btn-lg grow" disabled={release.isPending} onClick={confirm}>{release.isPending ? 'Releasing…' : 'Confirm release'}</button>
              </>
            )}
          </div>
        </div>
      )}
    </main>
  )
}
