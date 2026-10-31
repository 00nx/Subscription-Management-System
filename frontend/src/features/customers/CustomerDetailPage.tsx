import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useParams } from 'react-router-dom'
import { z } from 'zod'
import { PageContainer } from '@/components/layout/PageContainer'
import { ConfirmationDialog } from '@/components/shared/ConfirmationDialog'
import { ErrorState } from '@/components/shared/ErrorState'
import { FormField, TextAreaField } from '@/components/shared/FormField'
import { LoadingState } from '@/components/shared/LoadingState'
import { PageHeader } from '@/components/shared/PageHeader'
import { QueryTable } from '@/components/shared/QueryTable'
import { Section } from '@/components/shared/Section'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Button } from '@/components/ui/button'
import { useApiMutation } from '@/hooks/useApiMutation'
import { useListQuery } from '@/hooks/useListQuery'
import { date, money } from '@/lib/format'
import { applyServerError, required } from '@/lib/forms'
import { queryKeys } from '@/lib/queryKeys'
import { invoiceService } from '@/services/invoice.service'
import { paymentService } from '@/services/payment.service'
import { customerService, subscriptionService } from '@/services/sales.service'

const schema = z.object({ full_name: required('Name'), phone: z.string(), company_name: z.string(), billing_address: z.string(), tax_id: z.string() })
type Values = z.infer<typeof schema>

export default function CustomerDetailPage() {
  const { id = '' } = useParams()
  const [confirm, setConfirm] = useState(false)
  const query = useQuery({ queryKey: queryKeys.customers.detail(id), queryFn: () => customerService.get(id) })
  const subs = useListQuery(queryKeys.subscriptions.list, subscriptionService.list, { customer_id: id, page_size: 10 })
  const invoices = useListQuery(queryKeys.invoices.list, invoiceService.list, { customer_id: id, page_size: 10 })
  const payments = useListQuery(queryKeys.payments.list, paymentService.list, { customer_id: id, page_size: 10 })
  const { register, handleSubmit, reset, setError, formState: { errors, isDirty } } = useForm<Values>({ resolver: zodResolver(schema) })
  const c = query.data
  useEffect(() => { if (c) reset({ full_name: c.full_name, phone: c.phone ?? '', company_name: c.company_name ?? '', billing_address: c.billing_address ?? '', tax_id: c.tax_id ?? '' }) }, [c, reset])

  const save = useApiMutation((v: Values) => customerService.update(id, v), { invalidate: [queryKeys.customers.all], success: 'Customer updated' })
  const toggle = useApiMutation(() => customerService.update(id, { is_active: !c!.is_active }), { invalidate: [queryKeys.customers.all], success: 'Account status updated', onSuccess: () => setConfirm(false) })

  if (query.isLoading) return <PageContainer><LoadingState /></PageContainer>
  if (!c) return <PageContainer><ErrorState message={query.error?.message} onRetry={() => query.refetch()} /></PageContainer>
  return (
    <PageContainer>
      <PageHeader title={c.full_name} description={`${c.customer_number} · customer since ${date(c.created_at)}`}
        actions={<><StatusBadge status={c.is_active ? 'active' : 'inactive'} /><Button variant={c.is_active ? 'destructive' : 'default'} size="sm" onClick={() => setConfirm(true)}>{c.is_active ? 'Deactivate' : 'Activate'}</Button></>} />
      <Section title="Profile">
        <form className="grid gap-4 sm:grid-cols-2" noValidate onSubmit={handleSubmit((v) => save.mutateAsync(v).catch((e) => applyServerError(e, setError)))}>
          <FormField label="Full name" error={errors.full_name?.message} {...register('full_name')} />
          <FormField label="Email" value={c.email} disabled readOnly />
          <FormField label="Phone" {...register('phone')} />
          <FormField label="Company" {...register('company_name')} />
          <FormField label="Tax ID" {...register('tax_id')} />
          <div className="sm:col-span-2"><TextAreaField label="Billing address" {...register('billing_address')} /></div>
          <div className="sm:col-span-2"><Button type="submit" disabled={!isDirty || save.isPending}>Save changes</Button></div>
        </form>
      </Section>
      <Section title="Subscriptions" flush>
        <QueryTable bare query={subs} page={1} onPage={() => undefined} rowKey={(s) => s.id} emptyTitle="No subscriptions" columns={[
          { header: 'Number', cell: (s) => <Link className="text-primary hover:underline" to={`/subscriptions/${s.id}`}>{s.number}</Link> },
          { header: 'Plan', cell: (s) => s.plan_name }, { header: 'Status', cell: (s) => <StatusBadge status={s.status} /> },
          { header: 'Next billing', cell: (s) => date(s.next_billing_date) }, { header: 'Total', cell: (s) => money(s.total) }]} />
      </Section>
      <Section title="Invoices" flush>
        <QueryTable bare query={invoices} page={1} onPage={() => undefined} rowKey={(i) => i.id} emptyTitle="No invoices" columns={[
          { header: 'Number', cell: (i) => <Link className="text-primary hover:underline" to={`/invoices/${i.id}`}>{i.number}</Link> },
          { header: 'Status', cell: (i) => <StatusBadge status={i.is_overdue ? 'OVERDUE' : i.status} /> }, { header: 'Due', cell: (i) => date(i.due_date) },
          { header: 'Total', cell: (i) => money(i.total) }, { header: 'Outstanding', cell: (i) => money(i.outstanding) }]} />
      </Section>
      <Section title="Payment history" flush>
        <QueryTable bare query={payments} page={1} onPage={() => undefined} rowKey={(p) => p.id} emptyTitle="No payments" columns={[
          { header: 'Invoice', cell: (p) => p.invoice_number }, { header: 'Method', cell: (p) => p.method }, { header: 'Amount', cell: (p) => money(p.amount) },
          { header: 'Status', cell: (p) => <StatusBadge status={p.status} /> }, { header: 'Date', cell: (p) => date(p.payment_date ?? p.created_at) }]} />
      </Section>
      <ConfirmationDialog open={confirm} title={c.is_active ? 'Deactivate this customer?' : 'Activate this customer?'} destructive={c.is_active}
        description={c.is_active ? 'They will no longer be able to log in. Their subscriptions and invoices are kept.' : 'They will be able to log in again.'}
        confirmLabel={c.is_active ? 'Deactivate' : 'Activate'} onConfirm={() => toggle.mutate()} onCancel={() => setConfirm(false)} />
    </PageContainer>
  )
}
