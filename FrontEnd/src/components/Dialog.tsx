import { useEffect, useId, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { errorMessage } from '../api/client'
import { ErrorBanner } from './ui'

interface DialogProps {
  title: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  wide?: boolean
  /** A side panel on the right instead of a centred dialog. */
  panel?: boolean
}

export function Dialog({ title, onClose, children, footer, wide, panel }: DialogProps) {
  const titleId = useId()
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    const first = ref.current?.querySelector<HTMLElement>('input, select, textarea, button:not(.x-btn)')
    first?.focus()
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      previous?.focus()
    }
  }, [onClose])
  return (
    <div className={panel ? 'backdrop panel-backdrop' : 'backdrop'} onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div ref={ref} className={panel ? 'panel' : wide ? 'dialog dialog-wide' : 'dialog'} role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="dialog-head">
          <h2 id={titleId} style={{ fontSize: 20 }}>{title}</h2>
          <button type="button" className="x-btn" aria-label="Close" onClick={onClose}>×</button>
        </div>
        <div className="dialog-body">{children}</div>
        {footer && <div className="dialog-foot">{footer}</div>}
      </div>
    </div>
  )
}

interface ConfirmProps {
  title: string
  /** Restates the action, quantities and locations (UI_PAGES.md 3.6). */
  message: ReactNode
  confirmLabel?: string
  danger?: boolean
  onConfirm: () => Promise<unknown>
  onClose: () => void
}

/** Every action that changes stock or money asks first. */
export function ConfirmDialog({ title, message, confirmLabel = 'Confirm', danger, onConfirm, onClose }: ConfirmProps) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const go = async () => {
    setBusy(true)
    setError(null)
    try {
      await onConfirm()
      onClose()
    } catch (e) {
      setError(errorMessage(e))
      setBusy(false)
    }
  }
  return (
    <Dialog title={title} onClose={onClose} footer={<>
      <button type="button" className="btn btn-sec" onClick={onClose}>Cancel</button>
      <button type="button" className={danger ? 'btn btn-dan' : 'btn btn-pri'} onClick={go} disabled={busy}>{busy ? 'Working…' : confirmLabel}</button>
    </>}>
      <div style={{ fontSize: 15 }}>{message}</div>
      {error && <ErrorBanner text={error} />}
    </Dialog>
  )
}

interface ReasonProps {
  title: string
  /** What will happen. */
  message: ReactNode
  confirmLabel: string
  label?: string
  placeholder?: string
  onConfirm: (reason: string) => Promise<unknown>
  onClose: () => void
}

/** Reject, Cancel, Close, Void, Reverse, Correct and condition changes always need a reason. */
export function ReasonDialog({ title, message, confirmLabel, label = 'Reason', placeholder, onConfirm, onClose }: ReasonProps) {
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const id = useId()
  const go = async (e?: React.FormEvent) => {
    e?.preventDefault()
    if (!reason.trim()) { setError('A reason is required. It shows later in the history.'); return }
    setBusy(true)
    setError(null)
    try {
      await onConfirm(reason.trim())
      onClose()
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }
  return (
    <Dialog title={title} onClose={onClose} footer={<>
      <button type="button" className="btn btn-sec" onClick={onClose}>Back</button>
      <button type="button" className="btn btn-dan" onClick={() => go()} disabled={busy}>{busy ? 'Working…' : confirmLabel}</button>
    </>}>
      <div style={{ fontSize: 15 }}>{message}</div>
      <form className="fld" onSubmit={go}>
        <label htmlFor={id}>{label} <span className="muted">(required)</span></label>
        <textarea id={id} className="inp" value={reason} placeholder={placeholder} onChange={(e) => setReason(e.target.value)} maxLength={500} />
      </form>
      {error && <ErrorBanner text={error} />}
    </Dialog>
  )
}
