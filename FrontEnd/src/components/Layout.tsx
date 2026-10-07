import { useEffect, useState } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useApi, useLocations } from '../api/hooks'
import { ErrorBoundary } from './ErrorBoundary'
import type { Dashboard } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { formatEc, formatGreg, toEthiopian, todayAddis, weekdayName } from '../lib/ethiopian'
import { initials } from '../lib/format'
import { ROLE_LABEL } from '../lib/labels'
import { MENUS } from '../lib/nav'
import type { NavItem } from '../lib/nav'

const COLLAPSED_KEY = 'erp.sidebarCollapsed'

function readCollapsed(): boolean {
  try { return localStorage.getItem(COLLAPSED_KEY) === '1' } catch { return false }
}

/** Badges come from the dashboard call the home page makes anyway (refreshed every minute). */
function useBadges(): Partial<Record<NonNullable<NavItem['badge']>, number>> {
  const { data } = useApi<Dashboard>('/dashboard/', undefined, { refetchInterval: 60_000 })
  if (!data) return {}
  return {
    requests: data.request_queue?.by_status?.pending ?? data.request_queue?.items.filter((r) => r.status === 'pending').length,
    verify: data.payments_to_verify?.count,
    adjustments: data.adjustments_to_approve?.count,
    arriving: data.transfers_arriving?.count,
  }
}

export function Layout() {
  const { user } = useAuth()
  const [collapsed, setCollapsed] = useState(readCollapsed)
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const badges = useBadges()

  useEffect(() => { setOpen(false) }, [location.pathname])

  const toggle = () => {
    setCollapsed((c) => {
      try { localStorage.setItem(COLLAPSED_KEY, c ? '0' : '1') } catch { /* per-viewer convenience */ }
      return !c
    })
  }
  if (!user?.role) return null
  const sections = MENUS[user.role]
  // Highlight only the closest menu item: /sales/new is "New sale", not also "Sales".
  const path = location.pathname
  const activeTo = sections.flatMap((s) => s.items.map((i) => i.to))
    .filter((to) => (to === '/' ? path === '/' : path === to || path.startsWith(`${to}/`)))
    .sort((a, b) => b.length - a.length)[0]

  return (
    <div className="shell">
      {open && <div className="sidebar-scrim" onClick={() => setOpen(false)} />}
      <nav className={`sidebar${collapsed ? ' collapsed' : ''}${open ? ' open' : ''}`} aria-label="Main menu">
        <Link to="/" className="brand">
          <span className="brand-mark">F</span>
          <span className="brand-text"><span>Furniture ERP</span><span>Piassa · Denbel · Pawlos</span></span>
        </Link>
        {sections.map((section) => (
          <div className="nav-group" key={section.label}>
            <span className="nav-sec">{section.label}</span>
            {section.items.map((item) => {
              const count = item.badge ? badges[item.badge] : undefined
              return (
                <Link key={item.to} to={item.to} aria-current={item.to === activeTo ? 'page' : undefined}
                  className={item.to === activeTo ? 'nav-link active' : 'nav-link'}
                  title={collapsed ? item.label : undefined}>
                  <span className="nav-text">{item.label}</span>
                  {collapsed && <span aria-hidden="true">{item.label.charAt(0)}</span>}
                  {count ? <span className="nav-badge">{count}</span> : null}
                </Link>
              )
            })}
          </div>
        ))}
        <button type="button" className="collapse-btn" onClick={toggle}>{collapsed ? '»' : '« Collapse menu'}</button>
      </nav>
      <div className="main-col">
        <TopBar onMenu={() => setOpen(true)} />
        <ErrorBoundary resetKey={location.pathname}><Outlet /></ErrorBoundary>
      </div>
    </div>
  )
}

function TopBar({ onMenu }: { onMenu: () => void }) {
  const { user, logout } = useAuth()
  const { data: locations } = useLocations()
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const today = todayAddis()
  const home = locations?.find((l) => l.id === user?.home_location)
  const where = [ROLE_LABEL[user?.role ?? ''] ?? '', home?.name ?? (user?.role === 'admin' ? 'Owner' : 'Office')].filter(Boolean).join(' · ')

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (q.trim()) navigate(`/search?q=${encodeURIComponent(q.trim())}`)
  }

  return (
    <header className="topbar">
      <button type="button" className="menu-btn" aria-label="Open menu" onClick={onMenu}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16" /></svg>
      </button>
      <form role="search" className="search-box" onSubmit={submit}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#66706A" strokeWidth="2" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></svg>
        <input aria-label="Search everything" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Product code, customer, phone, SO / SR / PAY number…" />
        <button type="submit">Search</button>
      </form>
      <div className="today">
        <span>{formatEc(toEthiopian(today))}</span>
        <span>{weekdayName(today)} {formatGreg(today)}</span>
      </div>
      <div className="who">
        <Link to="/profile" className="me">
          <span className="avatar">{initials(user?.name || user?.username || '?')}</span>
          <span className="who-text"><span>{user?.name || user?.username}</span><span>{where}</span></span>
        </Link>
        <button type="button" className="btn btn-sec btn-sm" onClick={() => { logout(); navigate('/login') }}>Log out</button>
      </div>
    </header>
  )
}
