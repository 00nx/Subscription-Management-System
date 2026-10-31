import { Link } from 'react-router-dom'
import { PageContainer } from '@/components/layout/PageContainer'
import { FilterDropdown } from '@/components/shared/FilterDropdown'
import { PageHeader } from '@/components/shared/PageHeader'
import { QueryTable } from '@/components/shared/QueryTable'
import { SearchInput } from '@/components/shared/SearchInput'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Toolbar } from '@/components/shared/Toolbar'
import { useListQuery } from '@/hooks/useListQuery'
import { useUrlState } from '@/hooks/useUrlState'
import { date } from '@/lib/format'
import { queryKeys } from '@/lib/queryKeys'
import { customerService } from '@/services/sales.service'

export default function CustomersPage() {
  const u = useUrlState()
  const params = { q: u.value('q'), is_active: u.value('is_active'), page: u.page, sort: '-created_at' }
  const query = useListQuery(queryKeys.customers.list, customerService.list, params)
  return (
    <PageContainer>
      <PageHeader title="Customers" description="Search and manage customer accounts." />
      <Toolbar>
        <SearchInput value={u.value('q')} onChange={(v) => u.set('q', v)} placeholder="Search name, email, company or CUS-…" />
        <FilterDropdown label="Status" value={u.value('is_active')} onChange={(v) => u.set('is_active', v)} options={[{ label: 'Active', value: 'true' }, { label: 'Inactive', value: 'false' }]} />
      </Toolbar>
      <QueryTable query={query} page={u.page} onPage={u.setPage} rowKey={(c) => c.id} emptyTitle="No customers found" emptyDescription="Customers appear here when they register."
        columns={[
          { header: 'Customer', cell: (c) => <Link className="font-medium text-primary hover:underline" to={`/customers/${c.id}`}>{c.full_name}</Link> },
          { header: 'ID', cell: (c) => c.customer_number },
          { header: 'Email', cell: (c) => c.email },
          { header: 'Company', cell: (c) => c.company_name ?? '-' },
          { header: 'Status', cell: (c) => <StatusBadge status={c.is_active ? 'active' : 'inactive'} /> },
          { header: 'Joined', cell: (c) => date(c.created_at) },
        ]} />
    </PageContainer>
  )
}
