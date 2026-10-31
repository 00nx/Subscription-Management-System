import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { PageContainer } from '@/components/layout/PageContainer'
import { EmptyState } from '@/components/shared/EmptyState'
import { ErrorState } from '@/components/shared/ErrorState'
import { LoadingState } from '@/components/shared/LoadingState'
import { PageHeader } from '@/components/shared/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useListQuery } from '@/hooks/useListQuery'
import { date, money } from '@/lib/format'
import { queryKeys } from '@/lib/queryKeys'
import { planService } from '@/services/catalog.service'
import type { Plan } from '@/types'
import { SubscribeDialog } from './SubscribeDialog'

const PER: Record<string, string> = { DAILY: 'day', WEEKLY: 'week', MONTHLY: 'month', YEARLY: 'year' }

export default function CustomerPlansPage() {
  const query = useListQuery(queryKeys.plans.list, planService.list, { page_size: 50 })
  const [params, setParams] = useSearchParams()
  const [chosen, setChosen] = useState<Plan | null>(null)
  // /customer/plans?subscribe=<id> (from the public pricing page after sign-up) opens that plan's dialog
  const wanted = params.get('subscribe')
  const target = chosen ?? (wanted ? query.data?.items.find((p) => p.id === wanted) ?? null : null)
  const close = () => { setChosen(null); if (wanted) { params.delete('subscribe'); setParams(params, { replace: true }) } }
  return (
    <PageContainer>
      <PageHeader title="Available plans" description="Pick a plan and subscribe in a minute. Your first invoice is issued straight away." />
      {query.isLoading ? <LoadingState /> : !query.data ? <ErrorState message={query.error?.message} onRetry={() => query.refetch()} /> : query.data.items.length === 0 ? <Card><EmptyState title="No plans available right now" description="Please check back soon." /></Card> : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{query.data.items.map((p) => (
          <Card key={p.id}><CardHeader><CardTitle>{p.name}</CardTitle></CardHeader><CardContent className="space-y-2 text-sm">
            <p className="text-2xl font-semibold">{money(p.price)} <span className="text-sm font-normal text-muted-foreground">/ {PER[p.billing_frequency]}</span></p>
            {p.description && <p className="text-muted-foreground">{p.description}</p>}
            <p>Minimum quantity: {p.min_quantity}</p>{p.available_until && <p className="text-muted-foreground">Available until {date(p.available_until)}</p>}
            <Button className="mt-2 w-full" onClick={() => setChosen(p)}>Subscribe</Button>
          </CardContent></Card>))}</div>)}
      <SubscribeDialog plan={target} onClose={close} />
    </PageContainer>
  )
}
