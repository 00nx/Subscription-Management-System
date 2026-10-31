import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { LoadingState } from '@/components/shared/LoadingState'
import { useAuth } from '@/hooks/useAuth'
import type { Role } from '@/types'
import { homeFor } from './nav'

/** Navigation guard only. The API enforces the same rules independently. */
export function ProtectedRoute({ roles }: { roles?: Role[] }) {
  const { user, isLoading } = useAuth()
  const location = useLocation()
  if (isLoading) return <LoadingState />
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />
  if (roles && !roles.includes(user.role)) return <Navigate to="/unauthorized" replace />
  return <Outlet />
}

export function PublicOnlyRoute() {
  const { user, isLoading } = useAuth()
  if (isLoading) return <LoadingState />
  return user ? <Navigate to={homeFor(user.role)} replace /> : <Outlet />
}

export function HomeRedirect() {
  const { user, isLoading } = useAuth()
  if (isLoading) return <LoadingState />
  return <Navigate to={user ? homeFor(user.role) : '/login'} replace />
}
