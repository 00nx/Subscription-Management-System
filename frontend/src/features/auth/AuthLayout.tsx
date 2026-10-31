import { useEffect, type ReactNode } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export function AuthLayout({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  useEffect(() => { document.title = `${title} · Brightloop` }, [title])
  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <p className="text-sm font-semibold text-primary">Brightloop</p>
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent>{children}</CardContent>
      </Card>
    </div>
  )
}
