import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'
import type { NavItem } from '@/routes/nav'

export function Sidebar({ items, onNavigate }: { items: NavItem[]; onNavigate?: () => void }) {
  return (
    <aside className="flex h-full w-60 flex-col border-r border-border bg-card">
      <div className="flex h-14 items-center px-6 text-lg font-semibold text-primary">Brightloop</div>
      <nav aria-label="Main" className="flex-1 space-y-1 overflow-y-auto p-3">
        {items.map(({ label, to, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn('flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-muted', isActive && 'bg-primary/10 text-primary')
            }
          >
            <Icon className="h-4 w-4" aria-hidden />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
