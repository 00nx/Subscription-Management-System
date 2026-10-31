import { Link } from 'react-router-dom'
import { PageContainer } from '@/components/layout/PageContainer'
import { FilterDropdown } from '@/components/shared/FilterDropdown'
import { PageHeader } from '@/components/shared/PageHeader'
import { QueryTable } from '@/components/shared/QueryTable'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Toolbar } from '@/components/shared/Toolbar'
import { Button } from '@/components/ui/button'
import { useApiMutation } from '@/hooks/useApiMutation'
import { useListQuery } from '@/hooks/useListQuery'
import { useUrlState } from '@/hooks/useUrlState'
import { date, label, money } from '@/lib/format'
import { queryKeys } from '@/lib/queryKeys'
import { invoiceService } from '@/services/invoice.service'
import { invoiceStatus } from './InvoicesPage'

export default function CustomerInvoicesPage() {
  const u = useUrlState()
  const query = useListQuery(queryKeys.invoices.list, invoiceService.list, { status: u.value('status'), page: u.page, sort: '-issue_date' })
  const pdf = useApiMutation((i: { id: string; number: string }) => invoiceService.pdf(i), { success: 'Invoice downloaded' })
  return (
    <PageContainer>
      <PageHeader title="My invoices" description="View, download and pay your invoices." />
      <Toolbar><FilterDropdown label="Status" value={u.value('status')} onChange={(v) => u.set('status', v)} options={['CONFIRMED', 'PARTIALLY_PAID', 'PAID', 'CANCELLED'].map((s) => ({ label: label(s), value: s }))} /></Toolbar>
      <QueryTable query={query} page={u.page} onPage={u.setPage} rowKey={(i) => i.id} emptyTitle="No invoices yet" emptyDescription="Your invoices will appear here."
        columns={[
          { header: 'Invoice', cell: (i) => <Link className="font-medium text-primary hover:underline" to={`/customer/invoices/${i.id}`}>{i.number}</Link> }, { header: 'Issued', cell: (i) => date(i.issue_date) }, { header: 'Due', cell: (i) => date(i.due_date) },
          { header: 'Status', cell: (i) => <StatusBadge status={invoiceStatus(i)} /> }, { header: 'Total', cell: (i) => money(i.total, i.currency) }, { header: 'Outstanding', cell: (i) => money(i.outstanding, i.currency) },
          { header: '', cell: (i) => <Button variant="ghost" size="sm" onClick={() => pdf.mutate(i)}>PDF</Button> }]} />
    </PageContainer>
  )
}
