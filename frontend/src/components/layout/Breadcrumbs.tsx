import { ChevronRight } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'
import { segmentLabels } from '@/routes/nav'

export function Breadcrumbs() {
  const parts = useLocation().pathname.split('/').filter(Boolean)
  const crumbs = parts.map((seg, i) => ({ label: segmentLabels[seg] ?? 'Details', to: '/' + parts.slice(0, i + 1).join('/') }))
  return (
    <nav aria-label="Breadcrumb" className="mb-4 flex items-center gap-1 text-sm text-muted-foreground">
      {crumbs.map((c, i) => (
        <span key={c.to} className="flex items-center gap-1">
          {i > 0 && <ChevronRight className="h-3 w-3" aria-hidden />}
          {i === crumbs.length - 1 || c.to === '/customer' ? <span aria-current={i === crumbs.length - 1 ? 'page' : undefined} className={i === crumbs.length - 1 ? 'text-foreground' : ''}>{c.label}</span> : <Link to={c.to} className="hover:text-foreground">{c.label}</Link>}
        </span>
      ))}
    </nav>
  )
}
