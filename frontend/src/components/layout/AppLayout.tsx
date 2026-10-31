import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { navFor } from '@/routes/nav'
import { Header } from './Header'
import { Sidebar } from './Sidebar'

export function AppLayout() {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  if (!user) return null
  const items = navFor(user.role)
  return (
    <div className="flex h-screen">
      <div className="hidden md:block"><Sidebar items={items} /></div>
      {open && (
        <div className="fixed inset-0 z-40 md:hidden" onClick={() => setOpen(false)}>
          <div className="absolute inset-0 bg-black/40" />
          <div className="relative h-full w-60" onClick={(e) => e.stopPropagation()}><Sidebar items={items} onNavigate={() => setOpen(false)} /></div>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <Header onMenuClick={() => setOpen(true)} />
        <main className="flex-1 overflow-y-auto"><Outlet /></main>
      </div>
    </div>
  )
}
