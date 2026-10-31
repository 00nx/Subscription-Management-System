import { useNavigate } from 'react-router-dom'
import { PageContainer } from '@/components/layout/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { Card, CardContent } from '@/components/ui/card'
import { QuotationForm } from './QuotationForm'

export default function QuotationNewPage() {
  const navigate = useNavigate()
  return (
    <PageContainer>
      <PageHeader title="New quotation" description="Start from a template or build one line by line." />
      <Card><CardContent className="pt-6"><QuotationForm onSaved={(q) => navigate(`/quotations/${q.id}`)} /></CardContent></Card>
    </PageContainer>
  )
}
