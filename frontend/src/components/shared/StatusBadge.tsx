import { Badge } from '@/components/ui/badge'
import { label } from '@/lib/format'

type V = 'default' | 'success' | 'warning' | 'destructive' | 'info'
const VARIANTS: Record<string, V> = {
  ACTIVE: 'success', PAID: 'success', SUCCESS: 'success', APPROVED: 'success', CONFIRMED: 'info', ADMIN: 'info', QUOTATION: 'info',
  STAFF: 'warning', PENDING: 'warning', PARTIALLY_PAID: 'warning', PAUSED: 'warning', INACTIVE: 'destructive',
  OVERDUE: 'destructive', CANCELLED: 'destructive', CLOSED: 'destructive', FAILED: 'destructive', EXPIRED: 'destructive', REJECTED: 'destructive',
  active: 'success', inactive: 'destructive',
}

/** Maps a status string to a colour; unknown statuses fall back to neutral. */
export function StatusBadge({ status }: { status: string }) {
  return <Badge variant={VARIANTS[status] ?? 'default'}>{status === 'active' || status === 'inactive' ? status : label(status)}</Badge>
}
