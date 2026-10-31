import { PageContainer } from '@/components/layout/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Card, CardContent } from '@/components/ui/card'
import { useAuth } from '@/hooks/useAuth'

export default function ProfilePage() {
  const { user } = useAuth()
  return (
    <PageContainer>
      <PageHeader title="Profile" description="Your account details." />
      <Card>
        <CardContent className="grid gap-4 pt-6 sm:grid-cols-2">
          <div><p className="text-sm text-muted-foreground">Name</p><p>{user?.full_name}</p></div>
          <div><p className="text-sm text-muted-foreground">Email</p><p>{user?.email}</p></div>
          <div><p className="text-sm text-muted-foreground">Role</p>{user && <StatusBadge status={user.role} />}</div>
        </CardContent>
      </Card>
    </PageContainer>
  )
}
