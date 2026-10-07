import { useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { api, request, setSignedOutHandler, tokens } from '../api/client'
import type { Me, Permission, Role } from '../api/types'

interface AuthState {
  user: Me | null
  /** True until we know whether a saved session is still valid. */
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  refreshMe: () => Promise<void>
  /** Admins have every permission (UI_PAGES.md 3.2). */
  can: (permission: Permission) => boolean
  is: (...roles: Role[]) => boolean
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [user, setUser] = useState<Me | null>(null)
  const [loading, setLoading] = useState(Boolean(tokens.access || tokens.refresh))

  const signOutLocally = useCallback(() => {
    tokens.clear()
    setUser(null)
    queryClient.clear()
  }, [queryClient])

  useEffect(() => {
    setSignedOutHandler(() => {
      setUser(null)
      queryClient.clear()
    })
  }, [queryClient])

  const refreshMe = useCallback(async () => {
    setUser(await api.get<Me>('/auth/me/'))
  }, [])

  useEffect(() => {
    if (!tokens.access && !tokens.refresh) return
    refreshMe().catch(() => signOutLocally()).finally(() => setLoading(false))
  }, [refreshMe, signOutLocally])

  const login = useCallback(async (username: string, password: string) => {
    const data = await request<{ access: string; refresh: string }>('/auth/token/', {
      method: 'POST', body: { username, password }, anonymous: true,
    })
    tokens.set(data.access, data.refresh)
    queryClient.clear()
    await refreshMe()
  }, [queryClient, refreshMe])

  const value = useMemo<AuthState>(() => ({
    user,
    loading,
    login,
    logout: signOutLocally,
    refreshMe,
    can: (permission) => Boolean(user && (user.role === 'admin' || user.permissions.includes(permission))),
    is: (...roles) => Boolean(user?.role && roles.includes(user.role)),
  }), [user, loading, login, signOutLocally, refreshMe])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth outside AuthProvider')
  return ctx
}
