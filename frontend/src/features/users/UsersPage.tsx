import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { PageContainer } from '@/components/layout/PageContainer'
import { DataTable } from '@/components/shared/DataTable'
import { ErrorState } from '@/components/shared/ErrorState'
import { LoadingState } from '@/components/shared/LoadingState'
import { PageHeader } from '@/components/shared/PageHeader'
import { Pagination } from '@/components/shared/Pagination'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Card } from '@/components/ui/card'
import { queryKeys } from '@/lib/queryKeys'
import { userService } from '@/services/user.service'

const PAGE_SIZE = 10

export default function UsersPage() {
  const [page, setPage] = useState(1)
  const params = { page, page_size: PAGE_SIZE }
  const { data, isLoading, error, refetch } = useQuery({ queryKey: queryKeys.users.all, queryFn: () => userService.list(params) })

  return (
    <PageContainer>
      <PageHeader title="Users" description="Accounts registered in the system." />
      <Card>
        {isLoading ? <LoadingState /> : error || !data ? <ErrorState message={error?.message} onRetry={refetch} /> : (
          <>
            <DataTable
              rows={data.items}
              rowKey={(u) => u.id}
              columns={[
                { header: 'Name', cell: (u) => u.full_name },
                { header: 'Email', cell: (u) => u.email },
                { header: 'Role', cell: (u) => <StatusBadge status={u.role} /> },
                { header: 'Status', cell: (u) => <StatusBadge status={u.is_active ? 'active' : 'inactive'} /> },
              ]}
            />
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPageChange={setPage} />
          </>
        )}
      </Card>
    </PageContainer>
  )
}
