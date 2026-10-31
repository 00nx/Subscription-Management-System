import { useQuery } from '@tanstack/react-query'
import { Bell, LogOut, Menu } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { UserAvatar } from '@/components/shared/UserAvatar'
import { useAuth } from '@/hooks/useAuth'
import { queryKeys } from '@/lib/queryKeys'
import { notificationService } from '@/services/user.service'
import { HeaderSearch } from './HeaderSearch'

export function Header({ onMenuClick }: { onMenuClick: () => void }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const unread = useQuery({ queryKey: [...queryKeys.notifications.all, 'unread'], queryFn: notificationService.unread, refetchInterval: 30_000, enabled: !!user })
  if (!user) return null
  const count = unread.data?.count ?? 0
  const customer = user.role === 'CUSTOMER'
  return (
    <header className="flex h-14 items-center gap-3 border-b border-border bg-card px-4">
      <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open menu" onClick={onMenuClick}><Menu className="h-5 w-5" /></Button>
      {!customer && <HeaderSearch />}
      <div className="ml-auto flex items-center gap-3">
        <Link to={customer ? '/customer/notifications' : '/notifications'} aria-label={count ? `Notifications, ${count} unread` : 'Notifications'} className="relative rounded-md p-2 hover:bg-muted">
          <Bell className="h-5 w-5" aria-hidden />
          {count > 0 && <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold text-white">{count > 99 ? '99+' : count}</span>}
        </Link>
        <StatusBadge status={user.role} />
        <Link to={customer ? '/customer/profile' : '/account'} className="flex items-center gap-2 rounded-md px-1 hover:bg-muted" aria-label="My account">
          <span className="hidden text-sm sm:block">{user.full_name}</span>
          <UserAvatar name={user.full_name} />
        </Link>
        <Button variant="ghost" size="sm" onClick={async () => { await logout(); navigate('/login') }}><LogOut className="h-4 w-4" aria-hidden />Log out</Button>
      </div>
    </header>
  )
}
