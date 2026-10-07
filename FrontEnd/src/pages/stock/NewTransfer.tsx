import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import { useAction, useRealLocations } from '../../api/hooks'
import type { Transfer } from '../../api/types'
import { ConfirmDialog } from '../../components/Dialog'
import { LinesEditor, linesSummary } from '../../components/LinesEditor'
import type { EditorLine } from '../../components/LinesEditor'
import { Card, Field, PageHeader } from '../../components/ui'

// P-26 New manual transfer (accountant, admin) — moves stock without a request, e.g.
// Piassa → Denbel, or a damaged piece to Pawlos for repair (Q3).
export default function NewTransfer() {
  const navigate = useNavigate()
  const { data: locations } = useRealLocations()
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [note, setNote] = useState('')
  const [lines, setLines] = useState<EditorLine[]>([])
  const [confirm, setConfirm] = useState(false)
  const fromLoc = locations?.find((l) => String(l.id) === from)
  const toLoc = locations?.find((l) => String(l.id) === to)
  const save = useAction(() => api.post<Transfer>('/transfers/', {
    from_location: Number(from), to_location: Number(to), note,
    lines: lines.map((l) => ({ product: l.product.id, qty: l.qty, condition: l.condition ?? 'new' })),
  }), { success: (t) => `${(t as Transfer).number} sent — in transit to ${toLoc?.code}.`, onSuccess: (t) => navigate(`/transfers/${(t as Transfer).id}`), toastErrors: false })

  const freeFor = (l: EditorLine) => {
    if (!fromLoc) return undefined
    const cell = l.product.stock[fromLoc.code]
    if (!cell) return 0
    return l.condition === 'display' ? cell.display : l.condition === 'damaged' ? cell.damaged : cell.available
  }

  return (
    <main className="page" style={{ maxWidth: 1100 }}>
      <Link to="/transfers" style={{ fontSize: 14 }}>← Transfers</Link>
      <PageHeader title="New transfer" sub="Moves stock without a request. The destination receives it." />
      <Card>
        <div className="form-grid">
          <Field label="From">{(id) => (
            <select id={id} className="inp" value={from} onChange={(e) => setFrom(e.target.value)}>
              <option value="">Choose…</option>{locations?.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          )}</Field>
          <Field label="To" error={from && from === to ? 'Choose a different location.' : undefined}>{(id) => (
            <select id={id} className="inp" value={to} onChange={(e) => setTo(e.target.value)}>
              <option value="">Choose…</option>{locations?.map((l) => <option key={l.id} value={l.id} disabled={String(l.id) === from}>{l.name}</option>)}
            </select>
          )}</Field>
        </div>
        <LinesEditor lines={lines} onChange={setLines} conditions stockAt={fromLoc ? [fromLoc.code] : []} maxFor={freeFor} />
        <Field label="Note">{(id) => <input id={id} className="inp" value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Damaged chair to Pawlos for repair" maxLength={255} />}</Field>
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          <Link className="btn btn-sec" to="/transfers">Cancel</Link>
          <button type="button" className="btn btn-pri" disabled={!from || !to || from === to || !lines.length} onClick={() => setConfirm(true)}>Send transfer</button>
        </div>
      </Card>
      {confirm && (
        <ConfirmDialog title="Send transfer" message={<>Send <strong>{linesSummary(lines)}</strong> from {fromLoc?.name} to {toLoc?.name}? It stays In transit until {toLoc?.code} receives it.</>}
          confirmLabel="Send" onConfirm={() => save.mutateAsync(undefined)} onClose={() => setConfirm(false)} />
      )}
    </main>
  )
}
