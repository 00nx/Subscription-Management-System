import { keepPreviousData, useQuery, type QueryKey } from '@tanstack/react-query'
import type { Page } from '@/types'

type Params = Record<string, string | number | boolean | undefined>

/** Paginated list query that keeps showing the previous page while the next one loads (no flicker when filtering). */
export function useListQuery<T>(key: (p: Params) => QueryKey, fn: (p: Params) => Promise<Page<T>>, params: Params, enabled = true) {
  return useQuery({ queryKey: key(params), queryFn: () => fn(params), placeholderData: keepPreviousData, enabled })
}
