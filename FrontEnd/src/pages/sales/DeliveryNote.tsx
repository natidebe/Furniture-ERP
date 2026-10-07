import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { errorMessage, fileUrl } from '../../api/client'
import { ErrorBanner, Loading } from '../../components/ui'

// P-43 Delivery note: the server renders the A4 PDF (replacing the three-copy paper pad);
// it is shown here in a viewer with Print.
export default function DeliveryNote() {
  const { id } = useParams()
  const [url, setUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let made: string | null = null
    fileUrl(`/delivery-notes/${id}/pdf/`).then((u) => { made = u; setUrl(u) }).catch((e) => setError(errorMessage(e)))
    return () => { if (made) URL.revokeObjectURL(made) }
  }, [id])
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <header className="topbar no-print" style={{ justifyContent: 'space-between' }}>
        <Link to="/sales">← Sales</Link>
        <strong>Delivery note</strong>
        <div className="row">
          {url && <a className="btn btn-sec" href={url} download={`delivery-note-${id}.pdf`}>Download PDF</a>}
          {url && <button type="button" className="btn btn-pri" onClick={() => {
            const frame = document.getElementById('dn-frame') as HTMLIFrameElement | null
            frame?.contentWindow?.print()
          }}>Print</button>}
        </div>
      </header>
      {error && <div className="page"><ErrorBanner text={error} /></div>}
      {!url && !error && <Loading text="Preparing the delivery note…" />}
      {url && <iframe id="dn-frame" title="Delivery note" src={url} style={{ flex: 1, border: 0, width: '100%' }} />}
    </div>
  )
}
