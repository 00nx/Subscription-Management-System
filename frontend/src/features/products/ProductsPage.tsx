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
import { useAuth } from '@/hooks/useAuth'
import { useListQuery } from '@/hooks/useListQuery'
import { useUrlState } from '@/hooks/useUrlState'
import { money } from '@/lib/format'
import { queryKeys } from '@/lib/queryKeys'
import { productService } from '@/services/catalog.service'

export default function ProductsPage() {
  const { user } = useAuth()
  const u = useUrlState()
  const params = { q: u.value('q'), product_type: u.value('type'), status: u.value('status'), page: u.page, sort: u.value('sort') || '-created_at' }
  const query = useListQuery(queryKeys.products.list, productService.list, params)
  return (
    <PageContainer>
      <PageHeader title="Products" description="Products and their priced variants."
        actions={user?.role === 'ADMIN' ? <Button asChild><Link to="/products/new"><Plus className="h-4 w-4" aria-hidden />New product</Link></Button> : undefined} />
      <Toolbar>
        <SearchInput value={u.value('q')} onChange={(v) => u.set('q', v)} placeholder="Search products" />
        <FilterDropdown label="Type" value={u.value('type')} onChange={(v) => u.set('type', v)} options={['SERVICE', 'SOFTWARE', 'PHYSICAL', 'OTHER'].map((t) => ({ label: t, value: t }))} />
        <FilterDropdown label="Status" value={u.value('status')} onChange={(v) => u.set('status', v)} options={['ACTIVE', 'INACTIVE', 'ARCHIVED'].map((t) => ({ label: t, value: t }))} />
        <FilterDropdown label="Sort" value={u.value('sort')} onChange={(v) => u.set('sort', v)} options={[{ label: 'Name A-Z', value: 'name' }, { label: 'Price low-high', value: 'sales_price' }, { label: 'Price high-low', value: '-sales_price' }]} />
      </Toolbar>
      <QueryTable query={query} page={u.page} onPage={u.setPage} rowKey={(p) => p.id} emptyTitle="No products yet" emptyDescription="Products you create will appear here."
        columns={[
          { header: 'Name', cell: (p) => <Link className="font-medium text-primary hover:underline" to={`/products/${p.id}`}>{p.name}</Link> },
          { header: 'Type', cell: (p) => p.product_type }, { header: 'Sales price', cell: (p) => money(p.sales_price) },
          { header: 'Variants', cell: (p) => p.variants.length }, { header: 'Status', cell: (p) => <StatusBadge status={p.status} /> },
        ]} />
    </PageContainer>
  )
}
