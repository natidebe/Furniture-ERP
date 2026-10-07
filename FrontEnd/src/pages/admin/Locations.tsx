import { useState } from 'react'
import { ApiError, api } from '../../api/client'
import { useAction, useLocations } from '../../api/hooks'
import type { Location } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { Dialog } from '../../components/Dialog'
import { ErrorBanner, Field, Loading, PageHeader, StatusChip } from '../../components/ui'
import { label } from '../../lib/labels'

// P-81 Locations (admin edits; everyone reads). In Transit is a system location: shown, never edited.
export default function Locations() {
  const { is } = useAuth()
  const q = useLocations()
  const [editing, setEditing] = useState<Location | 'new' | null>(null)
  return (
    <main className="page">
      <PageHeader title="Locations" sub="Shops, the warehouse and sub-stores" actions={is('admin') && <button type="button" className="btn btn-pri" onClick={() => setEditing('new')}>New location</button>} />
      {q.isLoading ? <Loading /> : (
        <div className="tw">
          <table className="tbl">
            <thead><tr><th>Code</th><th>Name</th><th>Type</th><th>Part of</th><th>Sells</th><th>Releases stock</th><th>Status</th><th /></tr></thead>
            <tbody>
              {q.data?.map((l) => (
                <tr key={l.id}>
                  <td className="mono" style={{ fontWeight: 600 }}>{l.code}</td>
                  <td>{l.name}</td>
                  <td>{l.code === 'TRANSIT' ? 'System' : label(l.type)}</td>
                  <td>{l.parent ? q.data?.find((p) => p.id === l.parent)?.code : '—'}</td>
                  <td>{l.can_sell ? 'Yes' : '—'}</td>
                  <td>{l.can_release ? 'Yes' : '—'}</td>
                  <td><StatusChip kind="active" value={String(l.is_active)} /></td>
                  <td className="r">{is('admin') && l.code !== 'TRANSIT' && <button type="button" className="btn btn-sec btn-sm" onClick={() => setEditing(l)}>Edit</button>}{l.code === 'TRANSIT' && <span className="sub">Goods between locations</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {editing && <LocationDialog location={editing === 'new' ? null : editing} all={q.data ?? []} onClose={() => setEditing(null)} />}
    </main>
  )
}

function LocationDialog({ location, all, onClose }: { location: Location | null; all: Location[]; onClose: () => void }) {
  const [form, setForm] = useState({
    code: location?.code ?? '', name: location?.name ?? '', type: location?.type ?? 'shop', parent: location?.parent ? String(location.parent) : '',
    can_sell: location?.can_sell ?? true, can_release: location?.can_release ?? false, is_active: location?.is_active ?? true,
  })
  const [error, setError] = useState<unknown>(null)
  const save = useAction(() => {
    const body = { ...form, parent: form.parent ? Number(form.parent) : null }
    return location ? api.patch(`/locations/${location.id}/`, body) : api.post('/locations/', body)
  }, { success: 'Location saved.', onSuccess: onClose, toastErrors: false })
  const fields = error instanceof ApiError ? error.fields : {}
  return (
    <Dialog title={location ? `Edit ${location.code}` : 'New location'} onClose={onClose} footer={<>
      <button type="button" className="btn btn-sec" onClick={onClose}>Cancel</button>
      <button type="button" className="btn btn-pri" disabled={save.isPending} onClick={() => save.mutateAsync(undefined).catch(setError)}>Save</button>
    </>}>
      <div className="form-grid">
        <Field label="Code" error={fields.code}>{(id) => <input id={id} className="inp mono" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })} />}</Field>
        <Field label="Name" error={fields.name}>{(id) => <input id={id} className="inp" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />}</Field>
        <Field label="Type" error={fields.type}>{(id) => (
          <select id={id} className="inp" value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value as Location['type'] })}>
            <option value="shop">Shop</option><option value="warehouse">Warehouse</option><option value="sub_store">Sub-store</option>
          </select>
        )}</Field>
        <Field label="Part of" error={fields.parent}>{(id) => (
          <select id={id} className="inp" value={form.parent} onChange={(e) => setForm({ ...form, parent: e.target.value })}>
            <option value="">—</option>{all.filter((l) => l.code !== 'TRANSIT' && l.id !== location?.id).map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
          </select>
        )}</Field>
      </div>
      <label className="check"><input type="checkbox" checked={form.can_sell} onChange={(e) => setForm({ ...form, can_sell: e.target.checked })} />Can sell</label>
      <label className="check"><input type="checkbox" checked={form.can_release} onChange={(e) => setForm({ ...form, can_release: e.target.checked })} />Can release stock against requests (warehouse)</label>
      <label className="check"><input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />Active</label>
      {Boolean(error) && !Object.keys(fields).length && <ErrorBanner error={error} />}
    </Dialog>
  )
}
