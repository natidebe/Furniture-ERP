import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, download, errorMessage, request } from '../../api/client'
import { useQueryClient } from '@tanstack/react-query'
import { ErrorBanner, PageHeader } from '../../components/ui'
import { useToast } from '../../components/Toast'

interface Counts { dry_run: boolean; created: number; updated: number; price_changed: number; unchanged: number }

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <section className="card" style={{ padding: 24, display: 'flex', gap: 18, alignItems: 'flex-start' }}>
      <span style={{ width: 30, height: 30, borderRadius: 15, background: 'var(--sidebar)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, flex: 'none' }}>{n}</span>
      <div className="stack grow" style={{ gap: 12 }}><h2>{title}</h2>{children}</div>
    </section>
  )
}

// P-14 Import products: template → check (dry run) → import. One bad row stops everything.
export default function ImportProducts() {
  const [file, setFile] = useState<File | null>(null)
  const [check, setCheck] = useState<Counts | null>(null)
  const [rowErrors, setRowErrors] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<'check' | 'import' | null>(null)
  const [done, setDone] = useState<Counts | null>(null)
  const queryClient = useQueryClient()
  const toast = useToast()

  const send = async (dryRun: boolean) => {
    if (!file) return
    setBusy(dryRun ? 'check' : 'import')
    setError(null)
    setRowErrors([])
    const form = new FormData()
    form.append('file', file)
    form.append('dry_run', dryRun ? 'true' : 'false')
    try {
      const counts = await request<Counts>('/products/import/', { method: 'POST', body: form })
      if (dryRun) setCheck(counts)
      else {
        setDone(counts)
        setCheck(null)
        await queryClient.invalidateQueries()
        toast.show(`Imported: ${counts.created} created, ${counts.updated} updated.`)
      }
    } catch (e) {
      setCheck(null)
      if (e instanceof ApiError && Array.isArray((e.data as { errors?: string[] })?.errors)) {
        setRowErrors((e.data as { errors: string[] }).errors)
      } else setError(errorMessage(e))
    } finally {
      setBusy(null)
    }
  }

  const total = (c: Counts) => c.created + c.updated + c.price_changed + c.unchanged

  return (
    <main className="page" style={{ maxWidth: 1000 }}>
      <Link to="/products" style={{ fontSize: 14 }}>← Products</Link>
      <PageHeader title="Import products" />
      <Step n={1} title="Fill in the template">
        <span>Columns: <span className="mono">Code · Name · Category · Unit · Price · Wholesale price · Min stock · Description</span>. Existing codes are updated; new codes are created.</span>
        <div><button type="button" className="btn btn-sec" onClick={() => download('/products/import-template/', undefined, 'products-template.xlsx').catch((e) => setError(errorMessage(e)))}>Download template (.xlsx)</button></div>
      </Step>
      <Step n={2} title="Upload and check">
        <label style={{ display: 'flex', alignItems: 'center', gap: 14, padding: 16, border: '1px dashed var(--field)', borderRadius: 8, cursor: 'pointer', background: 'var(--surface-2)' }}>
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#1E4D40" strokeWidth="2" aria-hidden="true"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" /><path d="M14 3v6h6" /></svg>
          <span className="grow stack" style={{ gap: 2 }}>
            <span style={{ fontWeight: 600 }}>{file ? file.name : 'Choose the filled .xlsx file'}</span>
            <span className="sub">{file ? `${Math.ceil(file.size / 1024)} KB · ` : ''}.xlsx up to 5 MB</span>
          </span>
          <span style={{ color: 'var(--link)', fontWeight: 600 }}>{file ? 'Choose another file' : 'Browse'}</span>
          <input type="file" accept=".xlsx" className="sr-only" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setCheck(null); setRowErrors([]); setDone(null) }} />
        </label>
        <div><button type="button" className="btn btn-sec" disabled={!file || busy !== null} onClick={() => send(true)}>{busy === 'check' ? 'Checking…' : 'Check file'}</button></div>
      </Step>
      <Step n={3} title="Result of the check">
        {!check && !rowErrors.length && !done && !error && <span className="muted">Check a file to see what would change. Nothing is saved until you import.</span>}
        {error && <ErrorBanner text={error} />}
        {rowErrors.length > 0 && (
          <div role="alert" className="alert alert-err" style={{ flexDirection: 'column' }}>
            <strong>{rowErrors.length} {rowErrors.length === 1 ? 'problem' : 'problems'} — nothing was imported. Fix them and check again.</strong>
            <ul style={{ margin: 0, paddingLeft: 18 }}>{rowErrors.map((r) => <li key={r}>{r}</li>)}</ul>
          </div>
        )}
        {check && (
          <>
            <div className="grid-tiles">
              {([['created', 'will be created'], ['updated', 'will be updated'], ['price_changed', 'price changes'], ['unchanged', 'unchanged']] as const).map(([k, text]) => (
                <div key={k} className="tile"><span className="tile-value">{check[k]}</span><span className="sub">{text}</span></div>
              ))}
            </div>
            <span className="muted">Nothing is saved yet. Price changes are recorded in each product's price history.</span>
            <div><button type="button" className="btn btn-pri" disabled={busy !== null} onClick={() => send(false)}>{busy === 'import' ? 'Importing…' : `Import ${total(check)} rows`}</button></div>
          </>
        )}
        {done && <div className="alert alert-ok">Imported: {done.created} created, {done.updated} updated, {done.price_changed} price changes, {done.unchanged} unchanged. <Link to="/products">See products</Link></div>}
      </Step>
    </main>
  )
}
