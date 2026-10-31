import { useQuery } from '@tanstack/react-query'
import { CalendarClock, Repeat, Wallet } from 'lucide-react'
import { Link } from 'react-router-dom'
import { PageContainer } from '@/components/layout/PageContainer'
import { DataTable } from '@/components/shared/DataTable'
import { ErrorState } from '@/components/shared/ErrorState'
import { LoadingState } from '@/components/shared/LoadingState'
import { PageHeader } from '@/components/shared/PageHeader'
import { Section } from '@/components/shared/Section'
import { StatCard } from '@/components/shared/StatCard'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { useAuth } from '@/hooks/useAuth'
import { date, dateTime, label, money } from '@/lib/format'
import { queryKeys } from '@/lib/queryKeys'
import { invoiceStatus } from '@/features/invoices/InvoicesPage'
import { customerService } from '@/services/sales.service'

export default function CustomerDashboardPage() {
  const { user } = useAuth()
  const query = useQuery({ queryKey: queryKeys.summary, queryFn: customerService.summary })
  const s = query.data
  return (
    <PageContainer>
      <PageHeader title="Overview" description={`Welcome back, ${user?.full_name ?? ''}.`} />
      {query.isLoading ? <LoadingState /> : !s ? <ErrorState message={query.error?.message} onRetry={() => query.refetch()} /> : (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard label="Active subscriptions" value={s.active_subscriptions} icon={<Repeat className="h-5 w-5" />} />
            <StatCard label="Next billing date" value={date(s.next_billing_date)} icon={<CalendarClock className="h-5 w-5" />} />
            <StatCard label="Outstanding amount" value={money(s.outstanding_amount)} icon={<Wallet className="h-5 w-5" />} />
          </div>
          <Section title="Recent invoices" flush>
            <DataTable rows={s.recent_invoices} rowKey={(i) => i.id} emptyTitle="No invoices yet" emptyDescription="Invoices appear here once a subscription is billed." columns={[
              { header: 'Invoice', cell: (i) => <Link className="text-primary hover:underline" to={`/customer/invoices/${i.id}`}>{i.number}</Link> }, { header: 'Due', cell: (i) => date(i.due_date) },
              { header: 'Status', cell: (i) => <StatusBadge status={invoiceStatus(i)} /> }, { header: 'Total', cell: (i) => money(i.total, i.currency) }, { header: 'Outstanding', cell: (i) => money(i.outstanding, i.currency) }]} />
          </Section>
          <Section title="Recent payments" flush>
            <DataTable rows={s.recent_payments} rowKey={(p) => p.id} emptyTitle="No payments yet" columns={[
              { header: 'Date', cell: (p) => dateTime(p.payment_date ?? p.created_at) }, { header: 'Invoice', cell: (p) => p.invoice_number }, { header: 'Method', cell: (p) => label(p.method) },
              { header: 'Amount', cell: (p) => money(p.amount) }, { header: 'Status', cell: (p) => <StatusBadge status={p.status} /> }]} />
          </Section>
        </>)}
    </PageContainer>
  )
}
