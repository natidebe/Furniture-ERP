import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ApiError, api } from '../../api/client'
import { useAction, useApi, useCategories, useUnits } from '../../api/hooks'
import type { Product } from '../../api/types'
import { MoneyInput } from '../../components/inputs'
import { ErrorBanner, Field, Loading, PageHeader } from '../../components/ui'
import { money } from '../../lib/format'
import { ChangePriceDialog } from './ChangePriceDialog'

interface Form {
  code: string; name: string; category: string; unit: string; selling_price: string
  wholesale_price: string; min_stock: string; description: string; is_active: boolean
}

const EMPTY: Form = { code: '', name: '', category: '', unit: '', selling_price: '', wholesale_price: '', min_stock: '0', description: '', is_active: true }

// P-12 Product create / edit (admin). Prices are set on create only; afterwards Change price.
export default function ProductForm() {
  const { id } = useParams()
  const editing = Boolean(id)
  const navigate = useNavigate()
  const existing = useApi<Product>(editing ? `/products/${id}/` : null)
  const { data: categories } = useCategories()
  const { data: units } = useUnits()
  const [form, setForm] = useState<Form>(EMPTY)
  const [error, setError] = useState<unknown>(null)
  const [priceDialog, setPriceDialog] = useState<'selling' | 'wholesale' | null>(null)

  useEffect(() => {
    const p = existing.data
    if (p) {
      setForm({
        code: p.code, name: p.name, category: String(p.category), unit: String(p.unit),
        selling_price: p.selling_price, wholesale_price: p.wholesale_price ?? '', min_stock: String(p.min_stock),
        description: p.description ?? '', is_active: p.is_active ?? true,
      })
    }
  }, [existing.data])
  useEffect(() => {
    if (!editing && units?.length && !form.unit) setForm((f) => ({ ...f, unit: String(units[0].id) }))
  }, [editing, units, form.unit])

  const set = <K extends keyof Form>(key: K, value: Form[K]) => setForm((f) => ({ ...f, [key]: value }))
  const save = useAction(async () => {
    const body: Record<string, unknown> = {
      code: form.code, name: form.name, category: Number(form.category), unit: Number(form.unit),
      min_stock: Number(form.min_stock || 0), description: form.description, is_active: form.is_active,
    }
    if (!editing) {
      body.selling_price = form.selling_price
      body.wholesale_price = form.wholesale_price || null
    }
    return editing ? api.patch<Product>(`/products/${id}/`, body) : api.post<Product>('/products/', body)
  }, {
    success: (p) => (editing ? `${(p as Product).code} saved.` : `${(p as Product).code} created.`),
    onSuccess: (p) => navigate(`/products/${(p as Product).id}`),
    toastErrors: false,
  })

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    try { await save.mutateAsync(undefined) } catch (err) { setError(err) }
  }

  if (editing && existing.isLoading) return <main className="page"><Loading /></main>
  const fields = error instanceof ApiError ? error.fields : {}
  const wholesaleTooHigh = form.wholesale_price && form.selling_price && Number(form.wholesale_price) > Number(form.selling_price)

  return (
    <main className="page">
      <Link to={editing ? `/products/${id}` : '/products'} style={{ fontSize: 14 }}>← {editing ? `${existing.data?.code} ${existing.data?.name}` : 'Products'}</Link>
      <PageHeader title={editing ? 'Edit product' : 'New product'} />
      <form className="card card-pad" style={{ padding: 24, gap: 24, maxWidth: 960 }} onSubmit={submit}>
        <div className="form-grid">
          <Field label="Code" hint="Saved in capitals. Must be unique." error={fields.code}>{(fid) => <input id={fid} className="inp mono" required value={form.code} onChange={(e) => set('code', e.target.value.toUpperCase())} />}</Field>
          <Field label="Name" error={fields.name}>{(fid) => <input id={fid} className="inp" required value={form.name} onChange={(e) => set('name', e.target.value)} />}</Field>
          <Field label="Category" error={fields.category}>{(fid) => (
            <select id={fid} className="inp" required value={form.category} onChange={(e) => set('category', e.target.value)}>
              <option value="">Choose…</option>
              {categories?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          )}</Field>
          <Field label="Unit" error={fields.unit}>{(fid) => (
            <select id={fid} className="inp" required value={form.unit} onChange={(e) => set('unit', e.target.value)}>
              {units?.map((u) => <option key={u.id} value={u.id}>{u.symbol}</option>)}
            </select>
          )}</Field>
        </div>
        <div className="stack">
          <h2>Prices</h2>
          {editing ? (
            <div className="form-grid">
              <Field label="Selling price (ETB)">{(fid) => (
                <div className="row" style={{ flexWrap: 'nowrap', gap: 8 }}><input id={fid} className="inp num" readOnly value={money(form.selling_price)} /><button type="button" className="btn btn-sec" onClick={() => setPriceDialog('selling')}>Change</button></div>
              )}</Field>
              <Field label="Wholesale price (ETB)">{(fid) => (
                <div className="row" style={{ flexWrap: 'nowrap', gap: 8 }}><input id={fid} className="inp num" readOnly value={form.wholesale_price ? money(form.wholesale_price) : 'Not set'} /><button type="button" className="btn btn-sec" onClick={() => setPriceDialog('wholesale')}>Change</button></div>
              )}</Field>
            </div>
          ) : (
            <div className="form-grid">
              <Field label="Selling price" error={fields.selling_price}>{(fid) => <MoneyInput id={fid} value={form.selling_price} onChange={(v) => set('selling_price', v)} />}</Field>
              <Field label="Wholesale price (optional)" hint="What resellers pay. Empty: resellers pay the selling price."
                error={wholesaleTooHigh ? "Wholesale can't be above the selling price." : fields.wholesale_price}>
                {(fid) => <MoneyInput id={fid} value={form.wholesale_price} onChange={(v) => set('wholesale_price', v)} />}
              </Field>
            </div>
          )}
          <span className="fld-hint">Prices are set when a product is created. After that they change only through Change price, so every change is recorded. No cost price is kept.</span>
        </div>
        <div className="form-grid">
          <Field label="Minimum stock" hint="Low-stock alert when sellable stock falls below this." error={fields.min_stock}>{(fid) => <input id={fid} className="inp" inputMode="numeric" value={form.min_stock} onChange={(e) => set('min_stock', e.target.value.replace(/\D/g, ''))} />}</Field>
          <div className="fld"><span className="fld-label">Status</span><label className="check" style={{ height: 42 }}><input type="checkbox" checked={form.is_active} onChange={(e) => set('is_active', e.target.checked)} />Active — can be sold and requested</label></div>
        </div>
        <Field label="Description" error={fields.description}>{(fid) => <textarea id={fid} className="inp" rows={3} value={form.description} onChange={(e) => set('description', e.target.value)} />}</Field>
        {Boolean(error) && !Object.keys(fields).length && <ErrorBanner error={error} />}
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          <Link className="btn btn-sec" to={editing ? `/products/${id}` : '/products'}>Cancel</Link>
          <button type="submit" className="btn btn-pri" disabled={save.isPending || Boolean(wholesaleTooHigh)}>{editing ? 'Save changes' : 'Create product'}</button>
        </div>
      </form>
      {priceDialog && existing.data && <ChangePriceDialog product={existing.data} initialType={priceDialog} onClose={() => setPriceDialog(null)} />}
    </main>
  )
}
