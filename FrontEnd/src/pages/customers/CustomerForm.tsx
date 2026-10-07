import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ApiError, api } from '../../api/client'
import { useAction, useApi } from '../../api/hooks'
import type { Customer } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { MoneyInput } from '../../components/inputs'
import { Banner, ErrorBanner, Field, Loading, PageHeader } from '../../components/ui'
import { CUSTOMER_TYPES, label } from '../../lib/labels'

interface Form {
  name: string; phone: string; shop_name: string; city: string; type: string; notes: string
  credit_allowed: boolean; credit_limit: string; is_active: boolean
}
const EMPTY: Form = { name: '', phone: '', shop_name: '', city: '', type: 'walk_in', notes: '', credit_allowed: false, credit_limit: '', is_active: true }

/**
 * The customer fields, used by the page and by New sale's side panel. Credit fields are
 * editable only with approve_credit. A phone used by another customer is a warning, not an error.
 */
export function CustomerEditor({ customer, onSaved, onCancel }: {
  customer?: Customer
  onSaved: (c: Customer) => void
  onCancel: () => void
}) {
  const { can } = useAuth()
  const [form, setForm] = useState<Form>(EMPTY)
  const [error, setError] = useState<unknown>(null)
  const [warnings, setWarnings] = useState<string[]>([])
  const [saved, setSaved] = useState<Customer | null>(null)
  const credit = can('approve_credit')

  useEffect(() => {
    if (customer) {
      setForm({
        name: customer.name, phone: customer.phone ?? '', shop_name: customer.shop_name ?? '', city: customer.city ?? '',
        type: customer.type ?? 'walk_in', notes: customer.notes ?? '', credit_allowed: customer.credit_allowed ?? false,
        credit_limit: customer.credit_limit ?? '', is_active: customer.is_active ?? true,
      })
    }
  }, [customer])

  const set = <K extends keyof Form>(key: K, value: Form[K]) => setForm((f) => ({ ...f, [key]: value }))
  const save = useAction(() => {
    const body: Record<string, unknown> = {
      name: form.name, phone: form.phone, shop_name: form.shop_name, city: form.city, type: form.type,
      notes: form.notes, is_active: form.is_active,
    }
    if (credit) {
      body.credit_allowed = form.credit_allowed
      body.credit_limit = form.credit_allowed && form.credit_limit ? form.credit_limit : null
    }
    return customer ? api.patch<Customer & { warnings?: string[] }>(`/customers/${customer.id}/`, body) : api.post<Customer & { warnings?: string[] }>('/customers/', body)
  }, { toastErrors: false, success: customer ? 'Customer saved.' : 'Customer created.' })

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      const c = await save.mutateAsync(undefined) as Customer & { warnings?: string[] }
      if (c.warnings?.length) { setWarnings(c.warnings); setSaved(c) } else onSaved(c)
    } catch (err) { setError(err) }
  }
  const fields = error instanceof ApiError ? error.fields : {}

  if (saved) {
    return (
      <div className="stack">
        {warnings.map((w) => <Banner key={w} kind="warn">{w}</Banner>)}
        <span className="muted">Saved. Resellers may share a number, so this is only a warning.</span>
        <div><button type="button" className="btn btn-pri" onClick={() => onSaved(saved)}>Continue</button></div>
      </div>
    )
  }

  return (
    <form className="stack" style={{ gap: 18 }} onSubmit={submit}>
      <div className="form-grid">
        <Field label="Name" error={fields.name}>{(id) => <input id={id} className="inp" required value={form.name} onChange={(e) => set('name', e.target.value)} />}</Field>
        <Field label="Phone" error={fields.phone}>{(id) => <input id={id} className="inp" inputMode="tel" value={form.phone} onChange={(e) => set('phone', e.target.value)} placeholder="09…" />}</Field>
        <Field label="Shop / company" error={fields.shop_name}>{(id) => <input id={id} className="inp" value={form.shop_name} onChange={(e) => set('shop_name', e.target.value)} />}</Field>
        <Field label="City" error={fields.city}>{(id) => <input id={id} className="inp" value={form.city} onChange={(e) => set('city', e.target.value)} placeholder="Addis Ababa, Jimma, Bahir Dar…" />}</Field>
        <Field label="Type" hint="Resellers pay the wholesale price" error={fields.type}>{(id) => (
          <select id={id} className="inp" value={form.type} onChange={(e) => set('type', e.target.value)}>
            {CUSTOMER_TYPES.map((t) => <option key={t} value={t}>{label(t)}</option>)}
          </select>
        )}</Field>
      </div>
      <fieldset className="card" style={{ padding: 16, margin: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <legend className="lbl" style={{ padding: '0 4px' }}>Credit</legend>
        {!credit && <span className="sub">Only the accountant or admin can change credit terms.</span>}
        <label className="check"><input type="checkbox" disabled={!credit} checked={form.credit_allowed} onChange={(e) => set('credit_allowed', e.target.checked)} />Allowed to buy on credit</label>
        {form.credit_allowed && (
          <Field label="Credit limit" hint="Empty: no limit" error={fields.credit_limit} style={{ maxWidth: 280 }}>{(id) => <MoneyInput id={id} value={form.credit_limit} disabled={!credit} onChange={(v) => set('credit_limit', v)} placeholder="No limit" />}</Field>
        )}
      </fieldset>
      <Field label="Notes" error={fields.notes}>{(id) => <textarea id={id} className="inp" rows={2} value={form.notes} onChange={(e) => set('notes', e.target.value)} />}</Field>
      {customer && <label className="check"><input type="checkbox" checked={form.is_active} onChange={(e) => set('is_active', e.target.checked)} />Active</label>}
      {Boolean(error) && !Object.keys(fields).length && <ErrorBanner error={error} />}
      <div className="row" style={{ justifyContent: 'flex-end' }}>
        <button type="button" className="btn btn-sec" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn btn-pri" disabled={save.isPending}>{customer ? 'Save changes' : 'Create customer'}</button>
      </div>
    </form>
  )
}

// P-62 Customer create / edit.
export default function CustomerForm() {
  const { id } = useParams()
  const navigate = useNavigate()
  const existing = useApi<Customer>(id ? `/customers/${id}/` : null)
  if (id && existing.isLoading) return <main className="page"><Loading /></main>
  const back = id ? `/customers/${id}` : '/customers'
  return (
    <main className="page" style={{ maxWidth: 920 }}>
      <Link to={back} style={{ fontSize: 14 }}>← {id ? existing.data?.name : 'Customers'}</Link>
      <PageHeader title={id ? 'Edit customer' : 'New customer'} />
      <div className="card" style={{ padding: 24 }}>
        <CustomerEditor customer={existing.data} onSaved={(c) => navigate(`/customers/${c.id}`)} onCancel={() => navigate(back)} />
      </div>
    </main>
  )
}
