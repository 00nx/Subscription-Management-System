import { Badge } from '@/components/ui/badge'

const VARIANTS = {
  active: 'success', paid: 'success', ADMIN: 'info', STAFF: 'warning', CUSTOMER: 'default',
  pending: 'warning', draft: 'default', inactive: 'destructive', overdue: 'destructive', cancelled: 'destructive',
} as const

/** Maps a status string to a colour; unknown statuses fall back to neutral. */
export function StatusBadge({ status }: { status: string }) {
  const variant = VARIANTS[status as keyof typeof VARIANTS] ?? 'default'
  return <Badge variant={variant}>{status}</Badge>
}
