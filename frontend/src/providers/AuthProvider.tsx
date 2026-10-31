import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useEffect, useMemo, type ReactNode } from 'react'
import { queryKeys } from '@/lib/queryKeys'
import { authService } from '@/services/auth.service'
import type { LoginRequest, User } from '@/types'

export interface AuthState {
  user: User | null
  isLoading: boolean
  login: (body: LoginRequest) => Promise<User>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthState | null>(null)

/** The user (and therefore the role) always comes from the backend, never from local storage. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  const { data: user = null, isLoading } = useQuery({
    queryKey: queryKeys.auth.me,
    queryFn: authService.restoreSession,
    staleTime: Infinity,
    retry: false,
  })

  // Drop cached data from the previous user, but keep the `me` query itself: mounted observers are bound to it.
  const clear = useCallback(() => {
    qc.removeQueries({ predicate: (q) => q.queryKey[0] !== 'auth' })
    qc.setQueryData(queryKeys.auth.me, null)
  }, [qc])

  useEffect(() => {
    window.addEventListener('auth:expired', clear)
    return () => window.removeEventListener('auth:expired', clear)
  }, [clear])

  const value = useMemo<AuthState>(() => ({
    user,
    isLoading,
    login: async (body) => {
      const u = await authService.login(body)
      qc.setQueryData(queryKeys.auth.me, u)
      return u
    },
    logout: async () => {
      try { await authService.logout() } finally { clear() }
    },
  }), [user, isLoading, qc, clear])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
