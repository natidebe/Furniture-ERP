// The one way the app talks to the backend (/api/v1). It adds the access token, refreshes it
// silently when it expires (access 15 min, refresh 7 days, rotated), and turns error bodies into
// ApiError: business errors are 400 {"code", "detail"}, field errors 400 {"field": ["…"]}.

const BASE = '/api/v1'
const ACCESS = 'erp.access'
const REFRESH = 'erp.refresh'

function read(key: string): string | null {
  try { return localStorage.getItem(key) } catch { return null }
}
function write(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key)
    else localStorage.setItem(key, value)
  } catch { /* private window: tokens live for this tab only */ }
}

let memoryAccess: string | null = read(ACCESS)
let memoryRefresh: string | null = read(REFRESH)

export const tokens = {
  get access() { return memoryAccess },
  get refresh() { return memoryRefresh },
  set(access: string, refresh?: string) {
    memoryAccess = access
    write(ACCESS, access)
    if (refresh !== undefined) {
      memoryRefresh = refresh
      write(REFRESH, refresh)
    }
  },
  clear() {
    memoryAccess = null
    memoryRefresh = null
    write(ACCESS, null)
    write(REFRESH, null)
  },
}

let onSignedOut: () => void = () => {}
/** Called when the session can't be refreshed (refresh token expired or revoked). */
export function setSignedOutHandler(handler: () => void) {
  onSignedOut = handler
}

export class ApiError extends Error {
  status: number
  code?: string
  detail?: string
  /** Field errors: {"qty": ["Ensure this value is greater than or equal to 1."]}. */
  fields: Record<string, string[]>
  data: unknown

  constructor(status: number, data: unknown) {
    const body = (data && typeof data === 'object' ? data : {}) as Record<string, unknown>
    const detail = typeof body.detail === 'string' ? body.detail : undefined
    super(detail ?? `Request failed (${status})`)
    this.status = status
    this.data = data
    this.detail = detail
    this.code = typeof body.code === 'string' ? body.code : undefined
    this.fields = {}
    for (const [key, value] of Object.entries(body)) {
      if (key === 'detail' || key === 'code') continue
      if (Array.isArray(value)) this.fields[key] = value.map(flatten)
      else if (typeof value === 'string') this.fields[key] = [value]
      else if (value && typeof value === 'object') this.fields[key] = [flatten(value)]
    }
  }
}

function flatten(value: unknown): string {
  if (typeof value === 'string') return value
  if (Array.isArray(value)) return value.map(flatten).join(' ')
  if (value && typeof value === 'object') {
    return Object.entries(value)
      .map(([k, v]) => (k === 'non_field_errors' ? flatten(v) : `${k}: ${flatten(v)}`))
      .join(' ')
  }
  return String(value)
}

/** The sentence to show staff for any error (UI_PAGES.md 3.6). */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.detail && error.status !== 401) {
      if (error.status === 403 && /permission/i.test(error.detail) && !error.code) {
        return "You don't have permission to do this."
      }
      if (error.status === 404 && /No .* matches/i.test(error.detail)) {
        return 'Not found or not yours to see.'
      }
      return error.detail
    }
    if (error.status === 403) return "You don't have permission to do this."
    if (error.status === 404) return 'Not found or not yours to see.'
    if (error.status === 401) return 'Your session has ended. Log in again.'
    const fieldText = Object.entries(error.fields)
      .map(([k, v]) => (k === 'non_field_errors' ? v.join(' ') : `${k.replace(/_/g, ' ')}: ${v.join(' ')}`))
      .join(' · ')
    if (fieldText) return fieldText
    if (error.status >= 500) return 'The server had a problem. Try again, and tell the admin if it keeps happening.'
    return error.message
  }
  if (error instanceof TypeError) return 'Cannot reach the server. Check the connection.'
  return error instanceof Error ? error.message : 'Something went wrong.'
}

export type Params = Record<string, string | number | boolean | null | undefined>

export function buildQuery(params?: Params): string {
  if (!params) return ''
  const q = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === '') continue
    q.set(key, String(value))
  }
  const text = q.toString()
  return text ? `?${text}` : ''
}

let refreshing: Promise<boolean> | null = null

async function refreshAccess(): Promise<boolean> {
  const refresh = tokens.refresh
  if (!refresh) return false
  refreshing ??= (async () => {
    try {
      const res = await fetch(`${BASE}/auth/refresh/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh }),
      })
      if (!res.ok) return false
      const data = await res.json()
      tokens.set(data.access, data.refresh ?? refresh)
      return true
    } catch {
      return false
    } finally {
      setTimeout(() => { refreshing = null }, 0)
    }
  })()
  return refreshing
}

interface RequestOptions {
  method?: string
  params?: Params
  body?: unknown
  /** Return the raw Response (downloads). */
  raw?: boolean
  /** Don't try to refresh or sign out on 401 (the login call itself). */
  anonymous?: boolean
}

async function send(path: string, options: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  let body: BodyInit | undefined
  if (options.body instanceof FormData) {
    body = options.body
  } else if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }
  if (tokens.access && !options.anonymous) headers.Authorization = `Bearer ${tokens.access}`
  return fetch(`${BASE}${path}${buildQuery(options.params)}`, {
    method: options.method ?? 'GET', headers, body,
  })
}

async function parse(res: Response): Promise<unknown> {
  if (res.status === 204) return null
  const text = await res.text()
  if (!text) return null
  try { return JSON.parse(text) } catch { return text }
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let res = await send(path, options)
  if (res.status === 401 && !options.anonymous) {
    if (await refreshAccess()) {
      res = await send(path, options)
    }
    if (res.status === 401) {
      tokens.clear()
      onSignedOut()
    }
  }
  if (options.raw && res.ok) return res as unknown as T
  const data = await parse(res)
  if (!res.ok) throw new ApiError(res.status, data)
  return data as T
}

export const api = {
  get: <T>(path: string, params?: Params) => request<T>(path, { params }),
  post: <T>(path: string, body?: unknown, params?: Params) =>
    request<T>(path, { method: 'POST', body: body ?? {}, params }),
  patch: <T>(path: string, body: unknown) => request<T>(path, { method: 'PATCH', body }),
}

/** Download a file (Excel export, template, PDF) and hand it to the browser. */
export async function download(path: string, params?: Params, fallbackName = 'download') {
  const res = await request<Response>(path, { params, raw: true })
  const blob = await res.blob()
  const disposition = res.headers.get('Content-Disposition') ?? ''
  const name = /filename="?([^";]+)"?/.exec(disposition)?.[1] ?? fallbackName
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/** Fetch a file as an object URL (a PDF to show in a viewer). */
export async function fileUrl(path: string): Promise<string> {
  const res = await request<Response>(path, { raw: true })
  return URL.createObjectURL(await res.blob())
}
