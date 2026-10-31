import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { z } from 'zod'
import { PageContainer } from '@/components/layout/PageContainer'
import { ConfirmationDialog } from '@/components/shared/ConfirmationDialog'
import { DataTable } from '@/components/shared/DataTable'
import { ErrorState } from '@/components/shared/ErrorState'
import { FormField, CheckboxField } from '@/components/shared/FormField'
import { LoadingState } from '@/components/shared/LoadingState'
import { Modal } from '@/components/shared/Modal'
import { PageHeader } from '@/components/shared/PageHeader'
import { Field, Section } from '@/components/shared/Section'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useApiMutation } from '@/hooks/useApiMutation'
import { date, money } from '@/lib/format'
import { applyServerError, optionalInt, required } from '@/lib/forms'
import { queryKeys } from '@/lib/queryKeys'
import { quotationService } from '@/services/sales.service'
import { QuotationForm } from './QuotationForm'

const convertSchema = z.object({ start_date: required('Start date'), term_periods: optionalInt, auto_renew: z.boolean() })
type CV = z.infer<typeof convertSchema>

export default function QuotationDetailPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const [modal, setModal] = useState<'edit' | 'convert' | null>(null)
  const [confirm, setConfirm] = useState<'send' | 'confirm' | null>(null)
  const query = useQuery({ queryKey: queryKeys.quotations.detail(id), queryFn: () => quotationService.get(id) })
  const act = useApiMutation((a: 'send' | 'confirm') => quotationService.action(id, a), { invalidate: [queryKeys.quotations.all], success: (_, a) => (a === 'send' ? 'Quotation sent' : 'Quotation confirmed'), onSuccess: () => setConfirm(null) })
  const { register, handleSubmit, setError, formState: { errors } } = useForm<CV>({ resolver: zodResolver(convertSchema), defaultValues: { start_date: new Date().toISOString().slice(0, 10), term_periods: '', auto_renew: false } })
  const convert = useApiMutation((v: CV) => quotationService.convert(id, { start_date: v.start_date, term_periods: v.term_periods ? Number(v.term_periods) : undefined, auto_renew: v.auto_renew }),
    { invalidate: [queryKeys.quotations.all, queryKeys.subscriptions.all], success: 'Subscription created from quotation', onSuccess: (s) => navigate(`/subscriptions/${s.id}`) })

  const q = query.data
  if (query.isLoading) return <PageContainer><LoadingState /></PageContainer>
  if (!q) return <PageContainer><ErrorState message={query.error?.message} onRetry={() => query.refetch()} /></PageContainer>
  const expired = q.is_expired && q.status !== 'CONFIRMED'
  return (
    <PageContainer>
      <PageHeader title={q.number} description={`For ${q.customer_name}`} actions={<>
        <StatusBadge status={q.is_expired && q.status !== 'CONFIRMED' ? 'EXPIRED' : q.status} />
        {q.status === 'DRAFT' && <><Button size="sm" variant="outline" onClick={() => setModal('edit')}>Edit</Button><Button size="sm" onClick={() => setConfirm('send')}>Send to customer</Button></>}
        {q.status === 'QUOTATION' && <Button size="sm" disabled={expired} title={expired ? 'Expired quotations cannot be confirmed' : undefined} onClick={() => setConfirm('confirm')}>Confirm</Button>}
        {q.status === 'CONFIRMED' && !q.subscription_id && <Button size="sm" onClick={() => setModal('convert')}>Convert to subscription</Button>}
        {q.subscription_id && <Button asChild size="sm" variant="outline"><Link to={`/subscriptions/${q.subscription_id}`}>View subscription</Link></Button>}
      </>} />
      {expired && <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">This quotation expired on {date(q.expiry_date)} and can no longer be confirmed.</p>}
      <Card><CardContent className="grid gap-5 pt-6 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Issued">{date(q.issue_date)}</Field><Field label="Expires">{date(q.expiry_date)}</Field><Field label="Payment terms">{q.payment_terms_days} days</Field>
        <Field label="Sent">{date(q.sent_at)}</Field>{q.notes && <div className="sm:col-span-2 lg:col-span-4"><Field label="Notes">{q.notes}</Field></div>}
      </CardContent></Card>
      <Section title="Lines" flush>
        <DataTable rows={q.lines} rowKey={(l) => l.id} columns={[{ header: 'Description', cell: (l) => l.description }, { header: 'Qty', cell: (l) => l.quantity }, { header: 'Unit price', cell: (l) => money(l.unit_price) },
          { header: 'Tax', cell: (l) => `${l.tax_rate}%` }, { header: 'Line total', cell: (l) => money(l.line_total) }]} />
        <div className="space-y-1 border-t border-border p-4 text-right text-sm">
          <p>Subtotal: {money(q.subtotal)}</p>{Number(q.discount_total) > 0 && <p>Discount (estimate): -{money(q.discount_total)}</p>}<p>Tax: {money(q.tax_total)}</p><p className="text-base font-semibold">Total: {money(q.total)}</p>
        </div>
      </Section>

      <Modal open={modal === 'edit'} onClose={() => setModal(null)} wide title="Edit quotation" description="Only draft quotations can be edited."><QuotationForm quotation={q} onSaved={() => setModal(null)} /></Modal>
      <Modal open={modal === 'convert'} onClose={() => setModal(null)} title="Convert to subscription" description="Quoted prices are preserved. The subscription is created as Confirmed.">
        <form className="space-y-4" noValidate onSubmit={handleSubmit((v) => convert.mutateAsync(v).catch((e) => applyServerError(e, setError)))}>
          <FormField label="Start date" type="date" error={errors.start_date?.message} {...register('start_date')} />
          <FormField label="Term (billing periods)" inputMode="numeric" hint="Leave empty for open-ended." error={errors.term_periods?.message} {...register('term_periods')} />
          <CheckboxField label="Renew automatically" {...register('auto_renew')} />
          {errors.root && <p role="alert" className="text-sm text-destructive">{errors.root.message}</p>}
          <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setModal(null)}>Cancel</Button><Button type="submit" disabled={convert.isPending}>Create subscription</Button></div>
        </form>
      </Modal>
      {confirm && <ConfirmationDialog open title={confirm === 'send' ? 'Send this quotation?' : 'Confirm this quotation?'} confirmLabel={confirm === 'send' ? 'Send' : 'Confirm'}
        description={confirm === 'send' ? 'The customer will be able to see it and it can no longer be edited.' : 'Confirmed quotations can be converted into subscriptions.'} onConfirm={() => act.mutate(confirm)} onCancel={() => setConfirm(null)} />}
    </PageContainer>
  )
}
