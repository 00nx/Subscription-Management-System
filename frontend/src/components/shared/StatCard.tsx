import type { ReactNode } from 'react'
import { Card, CardContent } from '@/components/ui/card'

export function StatCard({ label, value, hint, icon }: { label: string; value: ReactNode; hint?: string; icon?: ReactNode }) {
  return (
    <Card>
      <CardContent className="flex items-start justify-between gap-2 p-5">
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="mt-1 text-2xl font-semibold tracking-tight">{value}</p>
          {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
        </div>
        {icon && <div className="text-muted-foreground" aria-hidden>{icon}</div>}
      </CardContent>
    </Card>
  )
}
