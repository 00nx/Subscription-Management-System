import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'

export function StatusPage({ code, title, description }: { code: string; title: string; description: string }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 p-4 text-center">
      <p className="text-sm font-semibold text-primary">{code}</p>
      <h1 className="text-2xl font-semibold">{title}</h1>
      <p className="text-sm text-muted-foreground">{description}</p>
      <Button asChild><Link to="/">Go home</Link></Button>
    </div>
  )
}
