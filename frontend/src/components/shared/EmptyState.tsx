import { Inbox } from 'lucide-react'
import type { ReactNode } from 'react'

export function EmptyState({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 p-12 text-center">
      <Inbox className="h-8 w-8 text-muted-foreground" aria-hidden />
      <h3 className="font-medium">{title}</h3>
      {description && <p className="max-w-sm text-sm text-muted-foreground">{description}</p>}
      {action}
    </div>
  )
}
