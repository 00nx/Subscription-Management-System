import { Play } from 'lucide-react'
import { Link } from 'react-router-dom'
import { PageContainer } from '@/components/layout/PageContainer'
import { FilterDropdown } from '@/components/shared/FilterDropdown'
import { PageHeader } from '@/components/shared/PageHeader'
import { QueryTable } from '@/components/shared/QueryTable'
import { Section } from '@/components/shared/Section'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/hooks/useAuth'
import { useApiMutation } from '@/hooks/useApiMutation'
import { useListQuery } from '@/hooks/useListQuery'
import { useUrlState } from '@/hooks/useUrlState'
import { date, dateTime, FREQUENCY_LABEL, money } from '@/lib/format'
import { queryKeys } from '@/lib/queryKeys'
import { billingService } from '@/services/invoice.service'

export default function BillingPage() {
  const { user } = useAuth()
  const u = useUrlState()
  const due = useListQuery(queryKeys.billing.list, billingService.due, { upcoming_days: u.value('days') || 0, page: u.page, page_size: 15 })
  const runs = useListQuery((p) => [...queryKeys.billing.list(p), 'runs'], billingService.runs, { page_size: 10 })
  const failures = useListQuery((p) => [...queryKeys.billing.list(p), 'failures'], billingService.failures, { page_size: 10 })
  const run = useApiMutation(() => billingService.run(), {
    invalidate: [queryKeys.billing.all, queryKeys.invoices.all, queryKeys.subscriptions.all],
    success: (r) => `Billing run: ${r.invoiced} invoice(s) generated, ${r.failed} failed, ${r.renewed} renewed, ${r.expired} expired`,
  })
  return (
    <PageContainer>
      <PageHeader title="Billing" description="The scheduler bills due subscriptions automatically every hour, with no one logged in. This page shows what is due and any failures."
        actions={user?.role === 'ADMIN' ? <Button onClick={() => run.mutate()} disabled={run.isPending}><Play className="h-4 w-4" aria-hidden />{run.isPending ? 'Running…' : 'Run billing now'}</Button> : undefined} />
      <Section title="Due for billing" flush actions={<FilterDropdown label="Window" value={u.value('days')} onChange={(v) => u.set('days', v)} options={[{ label: 'Next 7 days', value: '7' }, { label: 'Next 30 days', value: '30' }]} />}>
        <QueryTable bare query={due} page={u.page} onPage={u.setPage} rowKey={(s) => s.id} emptyTitle="Nothing due" emptyDescription="Every active subscription is billed up to date."
          columns={[{ header: 'Subscription', cell: (s) => <Link className="text-primary hover:underline" to={`/subscriptions/${s.id}`}>{s.number}</Link> }, { header: 'Customer', cell: (s) => s.customer_name }, { header: 'Plan', cell: (s) => s.plan_name },
            { header: 'Frequency', cell: (s) => FREQUENCY_LABEL[s.billing_frequency] }, { header: 'Due date', cell: (s) => date(s.next_billing_date) }, { header: 'Amount', cell: (s) => money(s.total) }, { header: 'Status', cell: (s) => <StatusBadge status={s.status} /> }]} />
      </Section>
      <Section title="Billing run history" flush>
        <QueryTable bare query={runs} page={1} onPage={() => undefined} rowKey={(r) => r.id} emptyTitle="No runs yet" emptyDescription="Every scheduled or manual run is recorded here."
          columns={[{ header: 'Started', cell: (r) => dateTime(r.started_at) }, { header: 'Trigger', cell: (r) => r.trigger === 'MANUAL' ? 'Manual' : 'Scheduled' }, { header: 'Status', cell: (r) => <StatusBadge status={r.status === 'COMPLETED' ? 'SUCCESS' : r.status === 'FAILED' ? 'FAILED' : 'PENDING'} /> },
            { header: 'Examined', cell: (r) => r.examined }, { header: 'Invoiced', cell: (r) => r.invoiced }, { header: 'Recovered', cell: (r) => r.recovered }, { header: 'Failed', cell: (r) => r.failed },
            { header: 'Renewed / expired', cell: (r) => `${r.renewed} / ${r.expired}` }]} />
      </Section>
      <Section title="Billing failures" flush>
        <QueryTable bare query={failures} page={1} onPage={() => undefined} rowKey={(f) => f.id} emptyTitle="No failures" emptyDescription="Failed subscriptions stay due and are retried automatically."
          columns={[{ header: 'When', cell: (f) => dateTime(f.created_at) }, { header: 'Subscription', cell: (f) => <Link className="text-primary hover:underline" to={`/subscriptions/${f.subscription_id}`}>Open</Link> }, { header: 'Error', cell: (f) => f.detail ?? '' }]} />
      </Section>
    </PageContainer>
  )
}
