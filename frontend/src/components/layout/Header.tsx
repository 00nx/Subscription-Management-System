import { LogOut, Menu } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { UserAvatar } from '@/components/shared/UserAvatar'
import { useAuth } from '@/hooks/useAuth'

export function Header({ onMenuClick }: { onMenuClick: () => void }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  if (!user) return null
  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-card px-4">
      <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open menu" onClick={onMenuClick}><Menu className="h-5 w-5" /></Button>
      <div className="ml-auto flex items-center gap-3">
        <StatusBadge status={user.role} />
        <span className="hidden text-sm sm:block">{user.full_name}</span>
        <UserAvatar name={user.full_name} />
        <Button variant="ghost" size="sm" onClick={async () => { await logout(); navigate('/login') }}>
          <LogOut className="h-4 w-4" aria-hidden />Log out
        </Button>
      </div>
    </header>
  )
}
