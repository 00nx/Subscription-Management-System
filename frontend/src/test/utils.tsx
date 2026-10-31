import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import { AuthProvider } from '@/providers/AuthProvider'
import { makeQueryClient, QueryProvider } from '@/providers/QueryProvider'
import { AppRoutes } from '@/routes/AppRoutes'
import { authService } from '@/services/auth.service'
import type { Role, User } from '@/types'

export const makeUser = (role: Role): User => ({
  id: '1', email: `${role.toLowerCase()}@example.com`, full_name: `Test ${role}`, role, is_active: true, created_at: '2026-01-01T00:00:00Z',
})

/** Renders the real route tree. `session` is what the (mocked) backend says about the current user. */
export function renderApp(path: string, session: Role | null = null) {
  vi.spyOn(authService, 'restoreSession').mockResolvedValue(session ? makeUser(session) : null)
  return render(
    <QueryProvider client={makeQueryClient()}>
      <AuthProvider>
        <MemoryRouter initialEntries={[path]}>
          <AppRoutes />
        </MemoryRouter>
      </AuthProvider>
    </QueryProvider>,
  )
}
