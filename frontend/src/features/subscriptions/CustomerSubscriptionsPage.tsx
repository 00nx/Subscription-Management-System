import { Link } from 'react-router-dom'
import { PageContainer } from '@/components/layout/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { QueryTable } from '@/components/shared/QueryTable'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { useListQuery } from '@/hooks/useListQuery'
import { useUrlState } from '@/hooks/useUrlState'
import { date, FREQUENCY_LABEL, money } from '@/lib/format'
import { queryKeys } from '@/lib/queryKeys'
import { subscriptionService } from '@/services/sales.service'

export default function CustomerSubscriptionsPage() {
  const u = useUrlState()
  const query = useListQuery(queryKeys.subscriptions.list, subscriptionService.list, { page: u.page, sort: '-created_at' })
  return (
    <PageContainer>
      <PageHeader title="My subscriptions" description="Your plans, billing dates and status." />
      <QueryTable query={query} page={u.page} onPage={u.setPage} rowKey={(s) => s.id} emptyTitle="No subscriptions yet" emptyDescription="Once our team sets up a subscription for you, it will appear here."
        columns={[
          { header: 'Subscription', cell: (s) => <Link className="font-medium text-primary hover:underline" to={`/customer/subscriptions/${s.id}`}>{s.number}</Link> }, { header: 'Plan', cell: (s) => s.plan_name },
          { header: 'Billing', cell: (s) => FREQUENCY_LABEL[s.billing_frequency] }, { header: 'Status', cell: (s) => <StatusBadge status={s.status} /> },
          { header: 'Next billing', cell: (s) => date(s.next_billing_date) }, { header: 'Amount', cell: (s) => money(s.total) }]} />
    </PageContainer>
  )
}
