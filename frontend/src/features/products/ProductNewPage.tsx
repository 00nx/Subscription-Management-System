import { useNavigate } from 'react-router-dom'
import { PageContainer } from '@/components/layout/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { Card, CardContent } from '@/components/ui/card'
import { ProductForm } from './ProductForm'

export default function ProductNewPage() {
  const navigate = useNavigate()
  return (
    <PageContainer>
      <PageHeader title="New product" description="Create a product, then add priced variants to it." />
      <Card><CardContent className="pt-6"><ProductForm onSaved={(p) => navigate(`/products/${p.id}`)} /></CardContent></Card>
    </PageContainer>
  )
}
