import { Plus } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { PageContainer } from '@/components/layout/PageContainer'
import { FilterDropdown } from '@/components/shared/FilterDropdown'
import { PageHeader } from '@/components/shared/PageHeader'
import { QueryTable } from '@/components/shared/QueryTable'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Toolbar } from '@/components/shared/Toolbar'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { useListQuery } from '@/hooks/useListQuery'
import { useUrlState } from '@/hooks/useUrlState'
import { dateTime, label, money } from '@/lib/format'
import { queryKeys } from '@/lib/queryKeys'
import { paymentService } from '@/services/payment.service'
import { RecordPaymentDialog } from './RecordPaymentDialog'

export default function PaymentsPage() {
  const u = useUrlState()
  const [recording, setRecording] = useState(false)
  const params = { status: u.value('status'), method: u.value('method'), date_from: u.value('from'), date_to: u.value('to'), page: u.page }
  const query = useListQuery(queryKeys.payments.list, paymentService.list, params)
  return (
    <PageContainer>
      <PageHeader title="Payments" description="Successful, pending and failed payments. Only successful payments count as received."
        actions={<Button onClick={() => setRecording(true)}><Plus className="h-4 w-4" aria-hidden />Record payment</Button>} />
      <Toolbar>
        <FilterDropdown label="Status" value={u.value('status')} onChange={(v) => u.set('status', v)} options={['SUCCESS', 'PENDING', 'FAILED', 'CANCELLED'].map((s) => ({ label: label(s), value: s }))} />
        <FilterDropdown label="Method" value={u.value('method')} onChange={(v) => u.set('method', v)} options={['CASH', 'BANK_TRANSFER', 'CARD', 'UPI', 'OTHER'].map((s) => ({ label: label(s), value: s }))} />
        <label className="flex items-center gap-1 text-sm">From <Input type="date" className="w-40" aria-label="From date" value={u.value('from')} onChange={(e) => u.set('from', e.target.value)} /></label>
        <label className="flex items-center gap-1 text-sm">To <Input type="date" className="w-40" aria-label="To date" value={u.value('to')} onChange={(e) => u.set('to', e.target.value)} /></label>
      </Toolbar>
      <QueryTable query={query} page={u.page} onPage={u.setPage} rowKey={(p) => p.id} emptyTitle="No payments yet" emptyDescription="Payments appear here when customers pay or staff record them."
        columns={[
          { header: 'Date', cell: (p) => dateTime(p.payment_date ?? p.created_at) }, { header: 'Invoice', cell: (p) => <Link className="text-primary hover:underline" to={`/invoices/${p.invoice_id}`}>{p.invoice_number}</Link> },
          { header: 'Method', cell: (p) => label(p.method) }, { header: 'Amount', cell: (p) => money(p.amount) }, { header: 'Status', cell: (p) => <StatusBadge status={p.status} /> },
          { header: 'Reference', cell: (p) => p.transaction_reference ?? '-' },
        ]} />
      <RecordPaymentDialog open={recording} onClose={() => setRecording(false)} />
    </PageContainer>
  )
}
