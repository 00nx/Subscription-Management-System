import { useNavigate } from 'react-router-dom'
import { Bell } from 'lucide-react'
import { PageContainer } from '@/components/layout/PageContainer'
import { EmptyState } from '@/components/shared/EmptyState'
import { ErrorState } from '@/components/shared/ErrorState'
import { LoadingState } from '@/components/shared/LoadingState'
import { PageHeader } from '@/components/shared/PageHeader'
import { Pagination } from '@/components/shared/Pagination'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/hooks/useAuth'
import { useApiMutation } from '@/hooks/useApiMutation'
import { useListQuery } from '@/hooks/useListQuery'
import { useUrlState } from '@/hooks/useUrlState'
import { dateTime } from '@/lib/format'
import { queryKeys } from '@/lib/queryKeys'
import { entityPath } from '@/routes/paths'
import { notificationService } from '@/services/user.service'
import type { AppNotification } from '@/types'

export default function NotificationsPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const u = useUrlState()
  const unreadOnly = u.value('unread') === '1'
  const query = useListQuery(queryKeys.notifications.list, notificationService.list, { page: u.page, unread_only: unreadOnly })
  const read = useApiMutation((id: string) => notificationService.read(id), { invalidate: [queryKeys.notifications.all] })
  const readAll = useApiMutation(() => notificationService.readAll(), { invalidate: [queryKeys.notifications.all], success: 'All notifications marked as read' })

  const open = (n: AppNotification) => {
    if (!n.read_at) read.mutate(n.id)
    const to = entityPath(user!.role, n.entity_type, n.entity_id)
    if (to) navigate(to)
  }
  return (
    <PageContainer>
      <PageHeader title="Notifications" description="Everything that happened on your account."
        actions={<><Button variant="outline" size="sm" onClick={() => u.set('unread', unreadOnly ? '' : '1')}>{unreadOnly ? 'Show all' : 'Unread only'}</Button><Button size="sm" onClick={() => readAll.mutate()}>Mark all as read</Button></>} />
      <Card>
        {query.isLoading ? <LoadingState /> : query.error || !query.data ? <ErrorState message={query.error?.message} onRetry={() => query.refetch()} /> :
          query.data.items.length === 0 ? <EmptyState title={unreadOnly ? 'No unread notifications' : 'No notifications yet'} description="Updates about subscriptions, invoices and payments show up here." /> : (
            <>
              <ul className="divide-y divide-border">
                {query.data.items.map((n) => (
                  <li key={n.id}>
                    <button type="button" onClick={() => open(n)} className="flex w-full items-start gap-3 px-5 py-4 text-left hover:bg-muted/50">
                      <Bell className={`mt-0.5 h-4 w-4 shrink-0 ${n.read_at ? 'text-muted-foreground' : 'text-primary'}`} aria-hidden />
                      <span className="flex-1">
                        <span className={`block text-sm ${n.read_at ? '' : 'font-semibold'}`}>{n.title}</span>
                        {n.message && <span className="block text-sm text-muted-foreground">{n.message}</span>}
                        <span className="mt-0.5 block text-xs text-muted-foreground">{dateTime(n.created_at)}</span>
                      </span>
                      {!n.read_at && <span className="mt-1 h-2 w-2 rounded-full bg-primary" aria-label="Unread" />}
                    </button>
                  </li>
                ))}
              </ul>
              <Pagination page={u.page} pageSize={query.data.page_size} total={query.data.total} onPageChange={u.setPage} />
            </>
          )}
      </Card>
    </PageContainer>
  )
}
