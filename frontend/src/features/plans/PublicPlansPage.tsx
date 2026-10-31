import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ErrorState } from '@/components/shared/ErrorState'
import { LoadingState } from '@/components/shared/LoadingState'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { date, money } from '@/lib/format'
import { planService } from '@/services/catalog.service'

const PER: Record<string, string> = { DAILY: 'day', WEEKLY: 'week', MONTHLY: 'month', YEARLY: 'year' }

/** Pricing page for visitors who are not logged in. "Sign up" carries the chosen plan through registration and login. */
export default function PublicPlansPage() {
  const query = useQuery({ queryKey: ['public', 'plans'], queryFn: () => planService.public() })
  return (
    <div className="mx-auto min-h-screen max-w-5xl space-y-6 p-6">
      <header className="flex items-center justify-between"><p className="text-lg font-semibold text-primary">Brightloop</p>
        <div className="flex gap-2"><Button asChild variant="outline"><Link to="/login">Log in</Link></Button><Button asChild><Link to="/register">Sign up</Link></Button></div></header>
      <div><h1 className="text-2xl font-semibold">Plans and pricing</h1><p className="text-muted-foreground">Create an account, pick a plan and you are subscribed in a minute.</p></div>
      {query.isLoading ? <LoadingState /> : !query.data ? <ErrorState message={query.error?.message} onRetry={() => query.refetch()} /> : query.data.length === 0 ? <p className="text-muted-foreground">No plans are open for subscription right now.</p> : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{query.data.map((p) => (
          <Card key={p.id}><CardHeader><CardTitle>{p.name}</CardTitle></CardHeader><CardContent className="space-y-2 text-sm">
            <p className="text-2xl font-semibold">{money(p.price)} <span className="text-sm font-normal text-muted-foreground">/ {PER[p.billing_frequency]}</span></p>
            {p.description && <p className="text-muted-foreground">{p.description}</p>}
            <p>Includes {p.product_name}. Minimum quantity: {p.min_quantity}</p>{p.available_until && <p className="text-muted-foreground">Available until {date(p.available_until)}</p>}
            <Button asChild className="mt-2 w-full"><Link to={`/register?plan=${p.id}`}>Sign up to subscribe</Link></Button>
          </CardContent></Card>))}</div>)}
    </div>
  )
}
