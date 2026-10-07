import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

/**
 * List filters kept in the address bar, so a filtered list can be bookmarked, shared and is
 * what a dashboard tile links to. Changing any filter goes back to page 1.
 */
export function useFilters<K extends string>(keys: readonly K[], defaults: Partial<Record<K, string>> = {}) {
  const [params, setParams] = useSearchParams()
  const values = useMemo(() => {
    const out = {} as Record<K, string>
    for (const key of keys) out[key] = params.get(key) ?? defaults[key] ?? ''
    return out
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params])
  const page = Number(params.get('page') ?? '1') || 1

  const set = useCallback((key: K, value: string) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev)
      if (value === '' && defaults[key] === undefined) next.delete(key)
      else next.set(key, value)
      next.delete('page')
      return next
    }, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [setParams])

  const setMany = useCallback((patch: Partial<Record<K, string>>) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev)
      for (const [key, value] of Object.entries(patch) as [K, string][]) {
        if (value === '' && defaults[key] === undefined) next.delete(key)
        else next.set(key, value)
      }
      next.delete('page')
      return next
    }, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [setParams])

  const setPage = useCallback((p: number) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev)
      if (p <= 1) next.delete('page')
      else next.set('page', String(p))
      return next
    })
  }, [setParams])

  return { values, set, setMany, page, setPage }
}

/** A search box that waits for the typing to stop before filtering. */
export function useDebounced<T>(value: T, ms = 300): T {
  const [out, setOut] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setOut(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return out
}
