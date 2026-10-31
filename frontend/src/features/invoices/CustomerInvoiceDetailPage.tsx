import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { PageContainer } from '@/components/layout/PageContainer'
import { ErrorState } from '@/components/shared/ErrorState'
import { LoadingState } from '@/components/shared/LoadingState'
import { PageHeader } from '@/components/shared/PageHeader'
import { QueryTable } from '@/components/shared/QueryTable'
import { Section } from '@/components/shared/Section'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Button } from '@/components/ui/button'
import { useApiMutation } from '@/hooks/useApiMutation'
import { useListQuery } from '@/hooks/useListQuery'
import { dateTime, label, money } from '@/lib/format'
import { queryKeys } from '@/lib/queryKeys'
import { invoiceService } from '@/services/invoice.service'
import { paymentService } from '@/services/payment.service'
import { InvoiceView } from './InvoiceView'
import { invoiceStatus } from './InvoicesPage'
import { PayInvoiceDialog } from './PayInvoiceDialog'

export default function CustomerInvoiceDetailPage() {
  const { id = '' } = useParams()
  const [paying, setPaying] = useState(false)
  const query = useQuery({ queryKey: queryKeys.invoices.detail(id), queryFn: () => invoiceService.get(id) })
  const payments = useListQuery(queryKeys.payments.list, paymentService.list, { invoice_id: id, page_size: 50 })
  const pdf = useApiMutation(() => invoiceService.pdf(query.data!), { success: 'Invoice downloaded' })
  const i = query.data
  if (query.isLoading) return <PageContainer><LoadingState /></PageContainer>
  if (!i) return <PageContainer><ErrorState message={query.error?.message} onRetry={() => query.refetch()} /></PageContainer>
  const payable = (i.status === 'CONFIRMED' || i.status === 'PARTIALLY_PAID') && Number(i.outstanding) > 0
  return (
    <PageContainer>
      <PageHeader title={i.number} description={i.subscription_number ? `Subscription ${i.subscription_number}` : undefined} actions={<>
        <StatusBadge status={invoiceStatus(i)} /><Button size="sm" variant="outline" onClick={() => pdf.mutate()}>Download PDF</Button>
        {payable && <Button size="sm" onClick={() => setPaying(true)}>Pay {money(i.outstanding, i.currency)}</Button>}</>} />
      <InvoiceView invoice={i}>
        <Section title="Payment history" flush>
          <QueryTable bare query={payments} page={1} onPage={() => undefined} rowKey={(p) => p.id} emptyTitle="No payments yet" columns={[
            { header: 'Date', cell: (p) => dateTime(p.payment_date ?? p.created_at) }, { header: 'Method', cell: (p) => label(p.method) }, { header: 'Amount', cell: (p) => money(p.amount) },
            { header: 'Status', cell: (p) => <StatusBadge status={p.status} /> }, { header: 'Reference', cell: (p) => p.transaction_reference ?? '-' }]} />
        </Section>
      </InvoiceView>
      <PayInvoiceDialog invoice={i} open={paying} onClose={() => setPaying(false)} />
    </PageContainer>
  )
}
