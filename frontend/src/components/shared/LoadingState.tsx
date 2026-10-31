import { Skeleton } from '@/components/ui/skeleton'

/** Skeleton placeholder shaped like a table, so the page does not jump when data arrives. The label is for screen readers. */
export function LoadingState({ label = 'Loading…', rows = 5 }: { label?: string; rows?: number }) {
  return (
    <div role="status" aria-busy="true" className="space-y-3 p-6">
      <span className="sr-only">{label}</span>
      <Skeleton className="h-8 w-1/3" />
      {Array.from({ length: rows }, (_, i) => <Skeleton key={i} className="h-10 w-full" />)}
    </div>
  )
}
