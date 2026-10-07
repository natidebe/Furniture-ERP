import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { useAction, useSettings } from '../../api/hooks'
import { useAuth } from '../../auth/AuthContext'
import { Card, ErrorBanner, EthDate, Field, Loading, PageHeader } from '../../components/ui'

// P-84 Settings (admin edits; everyone reads). The salesperson discount limit is the owner's
// (D13); it starts at 0%, so every discount needs approval until it is raised.
export default function Settings() {
  const { is } = useAuth()
  const q = useSettings()
  const [pct, setPct] = useState('')
  const [error, setError] = useState<unknown>(null)
  useEffect(() => { if (q.data) setPct(String(Number(q.data.max_salesperson_discount_pct))) }, [q.data])
  const save = useAction(() => api.patch('/settings/', { max_salesperson_discount_pct: pct || '0' }), { success: 'Settings saved.', toastErrors: false })
  if (q.isLoading) return <main className="page"><Loading /></main>
  const s = q.data
  return (
    <main className="page" style={{ maxWidth: 820 }}>
      <PageHeader title="Settings" />
      <Card title="Discounts">
        <Field label="Salesperson discount limit (%)" hint="Discounts above this need someone with approve_discounts (the accountant or admin). 0% means every discount needs approval.">
          {(id) => (
            <div className="row" style={{ flexWrap: 'nowrap', maxWidth: 220 }}>
              <input id={id} className="inp num" inputMode="decimal" disabled={!is('admin')} value={pct} onChange={(e) => setPct(e.target.value.replace(/[^\d.]/g, ''))} />
              <span>%</span>
            </div>
          )}
        </Field>
        {s?.updated_at && <span className="sub">Last changed <EthDate value={s.updated_at} />{s.updated_by_name && ` by ${s.updated_by_name}`}</span>}
        {Boolean(error) && <ErrorBanner error={error} />}
        {is('admin') && <div><button type="button" className="btn btn-pri" disabled={save.isPending || Number(pct) > 100} onClick={() => save.mutateAsync(undefined).catch(setError)}>Save</button></div>}
      </Card>
      <Card title="Later">
        <span className="muted">Company name and address on the delivery note, and other settings, will appear here.</span>
      </Card>
    </main>
  )
}
