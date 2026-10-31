import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { PageContainer } from '@/components/layout/PageContainer'
import { ConfirmationDialog } from '@/components/shared/ConfirmationDialog'
import { DataTable } from '@/components/shared/DataTable'
import { ErrorState } from '@/components/shared/ErrorState'
import { LoadingState } from '@/components/shared/LoadingState'
import { PageHeader } from '@/components/shared/PageHeader'
import { QueryTable } from '@/components/shared/QueryTable'
import { Field, Section } from '@/components/shared/Section'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useApiMutation } from '@/hooks/useApiMutation'
import { useListQuery } from '@/hooks/useListQuery'
import { date, dateTime, FREQUENCY_LABEL, label, money } from '@/lib/format'
import { queryKeys } from '@/lib/queryKeys'
import { invoiceService } from '@/services/invoice.service'
import { subscriptionService } from '@/services/sales.service'
import type { SubscriptionStatus } from '@/types'

type Action = 'confirm' | 'activate' | 'pause' | 'resume' | 'renew' | 'cancel'
const ACTIONS: Record<SubscriptionStatus, Action[]> = {
  DRAFT: ['confirm', 'cancel'], QUOTATION: ['confirm', 'cancel'], CONFIRMED: ['activate', 'cancel'], ACTIVE: ['pause', 'renew', 'cancel'],
  PAUSED: ['resume', 'cancel'], EXPIRED: ['renew', 'cancel'], CLOSED: [],
}
const COPY: Record<Action, { label: string; title: string; text: string; destructive?: boolean }> = {
  confirm: { label: 'Confirm', title: 'Confirm this subscription?', text: 'It will be ready to activate.' },
  activate: { label: 'Activate', title: 'Activate this subscription?', text: 'Billing starts: the first invoice is generated on its start date by the scheduler.' },
  pause: { label: 'Pause', title: 'Pause this subscription?', text: 'No invoices are generated while it is paused.' },
  resume: { label: 'Resume', title: 'Resume this subscription?', text: 'Billing periods that elapsed during the pause are skipped, not back-billed.' },
  renew: { label: 'Renew', title: 'Renew this subscription?', text: 'The term is extended by one more term. This is only possible near the end of the current term.' },
  cancel: { label: 'Close', title: 'Close this subscription?', text: 'This is permanent. No further invoices will be generated.', destructive: true },
}

const DONE: Record<Action, string> = { confirm: 'confirmed', activate: 'activated', pause: 'paused', resume: 'resumed', renew: 'renewed', cancel: 'closed' }

export default function SubscriptionDetailPage() {
  const { id = '' } = useParams()
  const [pending, setPending] = useState<Action | null>(null)
  const query = useQuery({ queryKey: queryKeys.subscriptions.detail(id), queryFn: () => subscriptionService.get(id) })
  const events = useQuery({ queryKey: [...queryKeys.subscriptions.detail(id), 'events'], queryFn: () => subscriptionService.events(id) })
  const invoices = useListQuery(queryKeys.invoices.list, invoiceService.list, { subscription_id: id, page_size: 12 })
  const requests = useListQuery(queryKeys.requests.list, subscriptionService.requests, { status: 'PENDING', page_size: 50 })
  const act = useApiMutation((a: Action) => subscriptionService.action(id, a), { invalidate: [queryKeys.subscriptions.all, queryKeys.requests.all], success: (_, a) => `Subscription ${DONE[a]}`, onSuccess: () => setPending(null) })
  const decide = useApiMutation((v: { id: string; approve: boolean }) => subscriptionService.decide(v.id, v.approve), { invalidate: [queryKeys.subscriptions.all, queryKeys.requests.all], success: (r) => `Request ${r.status.toLowerCase()}` })

  const s = query.data
  if (query.isLoading) return <PageContainer><LoadingState /></PageContainer>
  if (!s) return <PageContainer><ErrorState message={query.error?.message} onRetry={() => query.refetch()} /></PageContainer>
  const myRequests = requests.data?.items.filter((r) => r.subscription_id === s.id) ?? []
  return (
    <PageContainer>
      <PageHeader title={s.number} description={`${s.plan_name} · ${FREQUENCY_LABEL[s.billing_frequency]} billing`}
        actions={<><StatusBadge status={s.status} />{ACTIONS[s.status].map((a) => <Button key={a} size="sm" variant={COPY[a].destructive ? 'destructive' : 'outline'} onClick={() => setPending(a)}>{COPY[a].label}</Button>)}</>} />
      <Card><CardContent className="grid gap-5 pt-6 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Customer"><Link className="text-primary hover:underline" to={`/customers/${s.customer_id}`}>{s.customer_name}</Link></Field>
        <Field label="Start date">{date(s.start_date)}</Field><Field label="Expiry date">{date(s.expiry_date)}</Field><Field label="Next billing">{date(s.next_billing_date)}</Field>
        <Field label="Payment terms">{s.payment_terms_days} days</Field><Field label="Term">{s.term_periods ? `${s.term_periods} period(s)` : 'Open-ended'}</Field>
        <Field label="Renewals">{s.renewal_count}</Field><Field label="Auto-renew">{s.auto_renew ? 'Yes' : 'No'}</Field>
        {s.quotation_id && <Field label="Quotation"><Link className="text-primary hover:underline" to={`/quotations/${s.quotation_id}`}>View quotation</Link></Field>}
        {s.notes && <div className="sm:col-span-2 lg:col-span-4"><Field label="Notes">{s.notes}</Field></div>}
      </CardContent></Card>

      {myRequests.length > 0 && (
        <Section title="Customer requests awaiting a decision" flush>
          <DataTable rows={myRequests} rowKey={(r) => r.id} columns={[
            { header: 'Request', cell: (r) => label(r.request_type) }, { header: 'Reason', cell: (r) => r.reason ?? '-' }, { header: 'Submitted', cell: (r) => dateTime(r.created_at) },
            { header: '', cell: (r) => <div className="flex gap-2"><Button size="sm" onClick={() => decide.mutate({ id: r.id, approve: true })}>Approve</Button><Button size="sm" variant="outline" onClick={() => decide.mutate({ id: r.id, approve: false })}>Reject</Button></div> }]} />
        </Section>
      )}

      <Section title="Lines" flush>
        <DataTable rows={s.lines} rowKey={(l) => l.id} columns={[
          { header: 'Description', cell: (l) => l.description }, { header: 'Qty', cell: (l) => l.quantity }, { header: 'Unit price', cell: (l) => money(l.unit_price) },
          { header: 'Tax', cell: (l) => `${l.tax_rate}%` }, { header: 'Line total', cell: (l) => money(l.line_total) }]} />
        <div className="space-y-1 border-t border-border p-4 text-right text-sm">
          <p>Subtotal: {money(s.subtotal)}</p><p>Tax: {money(s.tax_total)}</p><p className="font-semibold">Per period: {money(s.total)}</p>
          <p className="text-xs text-muted-foreground">Before any discounts, which are applied when each invoice is generated.</p>
        </div>
      </Section>

      <Section title="Invoices" flush>
        <QueryTable bare query={invoices} page={1} onPage={() => undefined} rowKey={(i) => i.id} emptyTitle="No invoices yet" emptyDescription="Invoices are generated automatically when billing is due." columns={[
          { header: 'Invoice', cell: (i) => <Link className="text-primary hover:underline" to={`/invoices/${i.id}`}>{i.number}</Link> }, { header: 'Period', cell: (i) => `${date(i.period_start)} → ${date(i.period_end)}` },
          { header: 'Status', cell: (i) => <StatusBadge status={i.is_overdue ? 'OVERDUE' : i.status} /> }, { header: 'Total', cell: (i) => money(i.total) }, { header: 'Outstanding', cell: (i) => money(i.outstanding) }]} />
      </Section>

      <Section title="History" flush>
        <DataTable rows={events.data ?? []} rowKey={(e) => e.id} emptyTitle="No history" columns={[
          { header: 'When', cell: (e) => dateTime(e.created_at) }, { header: 'Event', cell: (e) => label(e.event_type) },
          { header: 'Status change', cell: (e) => (e.to_status ? `${e.from_status ? label(e.from_status) + ' → ' : ''}${label(e.to_status)}` : '-') }, { header: 'Detail', cell: (e) => e.detail ?? '' }]} />
      </Section>

      {pending && <ConfirmationDialog open title={COPY[pending].title} description={COPY[pending].text} confirmLabel={COPY[pending].label} destructive={COPY[pending].destructive} onConfirm={() => act.mutate(pending)} onCancel={() => setPending(null)} />}
    </PageContainer>
  )
}
