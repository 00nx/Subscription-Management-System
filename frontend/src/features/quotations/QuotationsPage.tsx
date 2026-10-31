import { Plus } from 'lucide-react'
import { Link } from 'react-router-dom'
import { PageContainer } from '@/components/layout/PageContainer'
import { FilterDropdown } from '@/components/shared/FilterDropdown'
import { PageHeader } from '@/components/shared/PageHeader'
import { QueryTable } from '@/components/shared/QueryTable'
import { SearchInput } from '@/components/shared/SearchInput'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Toolbar } from '@/components/shared/Toolbar'
import { Button } from '@/components/ui/button'
import { useListQuery } from '@/hooks/useListQuery'
import { useUrlState } from '@/hooks/useUrlState'
import { date, money } from '@/lib/format'
import { queryKeys } from '@/lib/queryKeys'
import { quotationService } from '@/services/sales.service'

export default function QuotationsPage() {
  const u = useUrlState()
  const query = useListQuery(queryKeys.quotations.list, quotationService.list, { q: u.value('q'), status: u.value('status'), page: u.page })
  return (
    <PageContainer>
      <PageHeader title="Quotations" description="Draft, send and confirm quotations, then convert them into subscriptions."
        actions={<><Button asChild variant="outline"><Link to="/quotations/templates">Templates</Link></Button><Button asChild><Link to="/quotations/new"><Plus className="h-4 w-4" aria-hidden />New quotation</Link></Button></>} />
      <Toolbar>
        <SearchInput value={u.value('q')} onChange={(v) => u.set('q', v)} placeholder="Search QUO-…" />
        <FilterDropdown label="Status" value={u.value('status')} onChange={(v) => u.set('status', v)} options={['DRAFT', 'QUOTATION', 'CONFIRMED'].map((s) => ({ label: s, value: s }))} />
      </Toolbar>
      <QueryTable query={query} page={u.page} onPage={u.setPage} rowKey={(q) => q.id} emptyTitle="No quotations yet" emptyDescription="Create a quotation for a customer to get started."
        columns={[
          { header: 'Number', cell: (q) => <Link className="font-medium text-primary hover:underline" to={`/quotations/${q.id}`}>{q.number}</Link> }, { header: 'Customer', cell: (q) => q.customer_name },
          { header: 'Status', cell: (q) => <StatusBadge status={q.is_expired && q.status !== 'CONFIRMED' ? 'EXPIRED' : q.status} /> }, { header: 'Expires', cell: (q) => <span className={q.is_expired && q.status !== 'CONFIRMED' ? 'text-destructive' : ''}>{date(q.expiry_date)}</span> },
          { header: 'Total', cell: (q) => money(q.total) },
        ]} />
    </PageContainer>
  )
}
