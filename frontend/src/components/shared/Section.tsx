import type { ReactNode } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export function Section({ title, actions, children, flush }: { title: string; actions?: ReactNode; children: ReactNode; flush?: boolean }) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-3">
        <CardTitle className="text-base">{title}</CardTitle>
        {actions && <div className="flex gap-2">{actions}</div>}
      </CardHeader>
      <CardContent className={flush ? 'p-0' : undefined}>{children}</CardContent>
    </Card>
  )
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <div className="mt-0.5 text-sm">{children || '-'}</div>
    </div>
  )
}
