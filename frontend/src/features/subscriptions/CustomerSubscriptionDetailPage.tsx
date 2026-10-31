import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { PageContainer } from '@/components/layout/PageContainer'
import { ConfirmationDialog } from '@/components/shared/ConfirmationDialog'
import { DataTable } from '@/components/shared/DataTable'
import { ErrorState } from '@/components/shared/ErrorState'
import { LoadingState } from '@/components/shared/LoadingState'
import { PageHeader } from '@/components/shared/PageHeader'
import { Field, Section } from '@/components/shared/Section'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useApiMutation } from '@/hooks/useApiMutation'
import { date, FREQUENCY_LABEL, money } from '@/lib/format'
import { queryKeys } from '@/lib/queryKeys'
import { subscriptionService } from '@/services/sales.service'

type Action = 'pause' | 'resume' | 'renew' | 'cancel'
const COPY: Record<Action, { label: string; title: string; text: string; destructive?: boolean; done: string }> = {
  pause: { label: 'Pause', title: 'Pause this subscription?', text: 'No invoices are generated while it is paused. You can resume at any time.', done: 'paused' },
  resume: { label: 'Resume', title: 'Resume this subscription?', text: 'Billing continues from the next period; periods missed while paused are not charged.', done: 'resumed' },
  renew: { label: 'Renew', title: 'Renew this subscription?', text: 'Your term is extended by one more term.', done: 'renewed' },
  cancel: { label: 'Close subscription', title: 'Close this subscription?', text: 'This is permanent. No further invoices will be generated.', destructive: true, done: 'closed' },
}

export default function CustomerSubscriptionDetailPage() {
  const { id = '' } = useParams()
  const [pending, setPending] = useState<Action | null>(null)
  const query = useQuery({ queryKey: queryKeys.subscriptions.detail(id), queryFn: () => subscriptionService.get(id) })
  const act = useApiMutation((a: Action) => subscriptionService.action(id, a), {
    invalidate: [queryKeys.subscriptions.all, queryKeys.invoices.all], success: (_, a) => `Subscription ${COPY[a].done}`, onSuccess: () => setPending(null),
  })
  const s = query.data
  if (query.isLoading) return <PageContainer><LoadingState /></PageContainer>
  if (!s) return <PageContainer><ErrorState message={query.error?.message} onRetry={() => query.refetch()} /></PageContainer>
  const today = new Date().toISOString().slice(0, 10)
  const can: Action[] = []
  if (s.status === 'ACTIVE') {
    if (s.allow_pause) can.push('pause')
    if (s.allow_renewal && s.renewal_opens && s.renewal_opens <= today) can.push('renew')
    if (s.allow_early_closure || !s.expiry_date || s.expiry_date <= today) can.push('cancel')
  } else if (s.status === 'PAUSED') can.push('resume', 'cancel')
  else if (s.status === 'EXPIRED' && s.allow_renewal) can.push('renew', 'cancel')
  else if (s.status === 'CONFIRMED') can.push('cancel')
  return (
    <PageContainer>
      <PageHeader title={s.number} description={`${s.plan_name} · ${FREQUENCY_LABEL[s.billing_frequency]} billing`} actions={<>
        <StatusBadge status={s.status} />
        {can.map((k) => <Button key={k} size="sm" variant={COPY[k].destructive ? 'destructive' : 'outline'} onClick={() => setPending(k)}>{COPY[k].label}</Button>)}</>} />
      <Card><CardContent className="grid gap-5 pt-6 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Started">{date(s.start_date)}</Field><Field label="Expires">{date(s.expiry_date)}</Field><Field label="Next billing date">{date(s.next_billing_date)}</Field>
        <Field label="Amount per period">{money(s.total)}</Field><Field label="Payment terms">{s.payment_terms_days} days</Field><Field label="Auto-renew">{s.auto_renew ? 'Yes' : 'No'}</Field>
      </CardContent></Card>
      <Section title="What's included" flush>
        <DataTable rows={s.lines} rowKey={(l) => l.id} columns={[{ header: 'Item', cell: (l) => l.description }, { header: 'Qty', cell: (l) => l.quantity }, { header: 'Unit price', cell: (l) => money(l.unit_price) }, { header: 'Tax', cell: (l) => `${l.tax_rate}%` }, { header: 'Total', cell: (l) => money(l.line_total) }]} />
      </Section>
      <ConfirmationDialog open={!!pending} title={pending ? COPY[pending].title : ''} description={pending ? COPY[pending].text : ''} confirmLabel={pending ? COPY[pending].label : undefined}
        destructive={pending ? COPY[pending].destructive : false} onConfirm={() => pending && act.mutate(pending)} onCancel={() => setPending(null)} />
    </PageContainer>
  )
}
