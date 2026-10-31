import type { UseQueryResult } from '@tanstack/react-query'
import type { Page } from '@/types'
import { Card } from '@/components/ui/card'
import { DataTable, type Column } from './DataTable'
import { ErrorState } from './ErrorState'
import { LoadingState } from './LoadingState'
import { Pagination } from './Pagination'

interface Props<T> {
  query: UseQueryResult<Page<T>>
  columns: Column<T>[]
  rowKey: (row: T) => string
  page: number
  onPage: (p: number) => void
  emptyTitle: string
  emptyDescription?: string
  bare?: boolean
}

/** Loading / error / empty / table / pagination for any paginated query: every list screen uses this. */
export function QueryTable<T>({ query, columns, rowKey, page, onPage, emptyTitle, emptyDescription, bare }: Props<T>) {
  const body = query.isLoading ? <LoadingState /> : query.error || !query.data ? <ErrorState message={query.error?.message} onRetry={() => query.refetch()} /> : (
    <>
      <DataTable columns={columns} rows={query.data.items} rowKey={rowKey} emptyTitle={emptyTitle} emptyDescription={emptyDescription} />
      {query.data.total > 0 && <Pagination page={page} pageSize={query.data.page_size} total={query.data.total} onPageChange={onPage} />}
    </>
  )
  return bare ? body : <Card>{body}</Card>
}
