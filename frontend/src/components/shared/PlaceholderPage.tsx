import { PageContainer } from '@/components/layout/PageContainer'
import { Card } from '@/components/ui/card'
import { EmptyState } from './EmptyState'
import { PageHeader } from './PageHeader'

/** Phase 1 stand-in for every module screen. Shows no data: nothing here is fabricated. */
export function PlaceholderPage({ title, description }: { title: string; description: string }) {
  return (
    <PageContainer>
      <PageHeader title={title} description={description} />
      <Card>
        <EmptyState title={`No ${title.toLowerCase()} yet`} description="This module is implemented in Phase 2." />
      </Card>
    </PageContainer>
  )
}
