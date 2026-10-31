import { useMutation, useQueryClient, type QueryKey } from '@tanstack/react-query'
import { useToast } from '@/providers/ToastProvider'

interface Options<TData, TVars> {
  /** Query key prefixes to invalidate after success (refetches every matching list/detail). */
  invalidate?: QueryKey[]
  success?: string | ((data: TData, vars: TVars) => string)
  onSuccess?: (data: TData, vars: TVars) => void
}

/** useMutation + success/failure toasts + cache invalidation, so every button behaves the same way. */
export function useApiMutation<TData, TVars = void>(fn: (vars: TVars) => Promise<TData>, opts: Options<TData, TVars> = {}) {
  const qc = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: fn,
    onSuccess: async (data, vars) => {
      await Promise.all((opts.invalidate ?? []).map((key) => qc.invalidateQueries({ queryKey: key })))
      if (opts.success) toast.success(typeof opts.success === 'function' ? opts.success(data, vars) : opts.success)
      opts.onSuccess?.(data, vars)
    },
    onError: (err: Error) => toast.error(err.message || 'Something went wrong'),
  })
}
