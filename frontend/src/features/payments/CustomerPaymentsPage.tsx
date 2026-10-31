import { Link } from 'react-router-dom'
import { PageContainer } from '@/components/layout/PageContainer'
import { FilterDropdown } from '@/components/shared/FilterDropdown'
import { PageHeader } from '@/components/shared/PageHeader'
import { QueryTable } from '@/components/shared/QueryTable'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Toolbar } from '@/components/shared/Toolbar'
import { useListQuery } from '@/hooks/useListQuery'
import { useUrlState } from '@/hooks/useUrlState'
import { dateTime, label, money } from '@/lib/format'
import { queryKeys } from '@/lib/queryKeys'
import { paymentService } from '@/services/payment.service'

export default function CustomerPaymentsPage() {
  const u = useUrlState()
  const query = useListQuery(queryKeys.payments.list, paymentService.list, { status: u.value('status'), page: u.page })
  return (
    <PageContainer>
      <PageHeader title="Payments" description="Your payment history." />
      <Toolbar><FilterDropdown label="Status" value={u.value('status')} onChange={(v) => u.set('status', v)} options={['SUCCESS', 'PENDING', 'FAILED', 'CANCELLED'].map((s) => ({ label: label(s), value: s }))} /></Toolbar>
      <QueryTable query={query} page={u.page} onPage={u.setPage} rowKey={(p) => p.id} emptyTitle="No payments yet" emptyDescription="Payments you make will be listed here."
        columns={[{ header: 'Date', cell: (p) => dateTime(p.payment_date ?? p.created_at) }, { header: 'Invoice', cell: (p) => <Link className="text-primary hover:underline" to={`/customer/invoices/${p.invoice_id}`}>{p.invoice_number}</Link> },
          { header: 'Method', cell: (p) => label(p.method) }, { header: 'Amount', cell: (p) => money(p.amount) }, { header: 'Status', cell: (p) => <StatusBadge status={p.status} /> }, { header: 'Reference', cell: (p) => p.transaction_reference ?? '-' }]} />
    </PageContainer>
  )
}
