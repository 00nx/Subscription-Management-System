import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { Plus } from 'lucide-react'
import { PageContainer } from '@/components/layout/PageContainer'
import { CustomerPicker } from '@/components/shared/CustomerPicker'
import { FilterDropdown } from '@/components/shared/FilterDropdown'
import { CheckboxField, FormField, SelectField, TextAreaField } from '@/components/shared/FormField'
import { VariantChecks } from '@/components/shared/VariantChecks'
import { Modal } from '@/components/shared/Modal'
import { PageHeader } from '@/components/shared/PageHeader'
import { QueryTable } from '@/components/shared/QueryTable'
import { SearchInput } from '@/components/shared/SearchInput'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Toolbar } from '@/components/shared/Toolbar'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { useApiMutation } from '@/hooks/useApiMutation'
import { useListQuery } from '@/hooks/useListQuery'
import { useUrlState } from '@/hooks/useUrlState'
import { date, FREQUENCY_LABEL, money } from '@/lib/format'
import { applyServerError, intField, optionalInt, required } from '@/lib/forms'
import { queryKeys } from '@/lib/queryKeys'
import { planService, productService } from '@/services/catalog.service'
import { subscriptionService } from '@/services/sales.service'

const schema = z.object({
  customer_id: required('Customer'), plan_id: required('Plan'), start_date: required('Start date'), term_periods: optionalInt, payment_terms_days: intField(0, 'Payment terms'),
  quantity: intField(1, 'Quantity'), variant_ids: z.array(z.string()), auto_renew: z.boolean(), notes: z.string(),
})
type Values = z.infer<typeof schema>
export const today = () => new Date().toISOString().slice(0, 10)

function CreateDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate()
  const plans = useQuery({ queryKey: queryKeys.plans.list({ active: true }), queryFn: () => planService.list({ status: 'ACTIVE', page_size: 100 }) })
  const { register, control, handleSubmit, watch, reset, setError, formState: { errors } } = useForm<Values>({
    resolver: zodResolver(schema), defaultValues: { customer_id: '', plan_id: '', start_date: today(), term_periods: '', payment_terms_days: '0', quantity: '1', variant_ids: [], auto_renew: false, notes: '' },
  })
  const plan = plans.data?.items.find((p) => p.id === watch('plan_id'))
  const product = useQuery({ queryKey: queryKeys.products.detail(plan?.product_id ?? ''), queryFn: () => productService.get(plan!.product_id), enabled: !!plan })
  const create = useApiMutation((v: Values) => subscriptionService.create({
    customer_id: v.customer_id, plan_id: v.plan_id, start_date: v.start_date, term_periods: v.term_periods ? Number(v.term_periods) : null, payment_terms_days: Number(v.payment_terms_days),
    auto_renew: v.auto_renew, notes: v.notes || null, lines: [{ product_id: plan!.product_id, variant_ids: v.variant_ids, quantity: Number(v.quantity) }],
  }), { invalidate: [queryKeys.subscriptions.all], success: 'Subscription created', onSuccess: (s) => { reset(); onClose(); navigate(`/subscriptions/${s.id}`) } })
  return (
    <Modal open={open} onClose={onClose} wide title="New subscription" description="Created as a draft; confirm and activate it from its detail page.">
      <form className="grid gap-4 sm:grid-cols-2" noValidate onSubmit={handleSubmit((v) => create.mutateAsync(v).catch((e) => applyServerError(e, setError)))}>
        <div className="sm:col-span-2"><Controller control={control} name="customer_id" render={({ field }) => <CustomerPicker value={field.value} onChange={field.onChange} error={errors.customer_id?.message} />} /></div>
        <SelectField label="Plan" error={errors.plan_id?.message} {...register('plan_id')}><option value="">Select a plan…</option>
          {plans.data?.items.filter((p) => p.is_available).map((p) => <option key={p.id} value={p.id}>{p.name} · {money(p.price)} / {FREQUENCY_LABEL[p.billing_frequency].toLowerCase()}</option>)}</SelectField>
        <div className="space-y-1"><span className="text-sm font-medium">Variants</span>
          <Controller control={control} name="variant_ids" render={({ field }) => <VariantChecks variants={product.data?.variants ?? []} value={field.value} onChange={field.onChange} />} />
          <p className="text-xs text-muted-foreground">Each selected variant adds its additional price.</p></div>
        <FormField label="Quantity" inputMode="numeric" hint={plan ? `Plan minimum: ${plan.min_quantity}` : undefined} error={errors.quantity?.message} {...register('quantity')} />
        <FormField label="Start date" type="date" error={errors.start_date?.message} {...register('start_date')} />
        <FormField label="Term (billing periods)" inputMode="numeric" hint="Leave empty for open-ended." error={errors.term_periods?.message} {...register('term_periods')} />
        <FormField label="Payment terms (days)" inputMode="numeric" error={errors.payment_terms_days?.message} {...register('payment_terms_days')} />
        <div className="sm:col-span-2"><CheckboxField label="Renew automatically at the end of the term" {...register('auto_renew')} /></div>
        <div className="sm:col-span-2"><TextAreaField label="Notes" {...register('notes')} /></div>
        {errors.root && <p role="alert" className="text-sm text-destructive sm:col-span-2">{errors.root.message}</p>}
        <div className="flex justify-end gap-2 sm:col-span-2"><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button type="submit" disabled={create.isPending}>Create subscription</Button></div>
      </form>
    </Modal>
  )
}

const STATUSES = ['DRAFT', 'QUOTATION', 'CONFIRMED', 'ACTIVE', 'PAUSED', 'EXPIRED', 'CLOSED']

export default function SubscriptionsPage() {
  const u = useUrlState()
  const [creating, setCreating] = useState(false)
  const params = { q: u.value('q'), status: u.value('status'), billing_frequency: u.value('frequency'), plan_id: u.value('plan_id'), start_from: u.value('start_from'), start_to: u.value('start_to'), expiry_from: u.value('expiry_from'), expiry_to: u.value('expiry_to'), page: u.page, sort: '-created_at' }
  const query = useListQuery(queryKeys.subscriptions.list, subscriptionService.list, params)
  return (
    <PageContainer>
      <PageHeader title="Subscriptions" description="Customer subscriptions and their lifecycle." actions={<Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" aria-hidden />New subscription</Button>} />
      <Toolbar>
        <SearchInput value={u.value('q')} onChange={(v) => u.set('q', v)} placeholder="Search number, customer, email…" />
        <FilterDropdown label="Status" value={u.value('status')} onChange={(v) => u.set('status', v)} options={STATUSES.map((s) => ({ label: s, value: s }))} />
        <FilterDropdown label="Frequency" value={u.value('frequency')} onChange={(v) => u.set('frequency', v)} options={Object.entries(FREQUENCY_LABEL).map(([value, label]) => ({ label, value }))} />
        {([['start_from', 'Start from'], ['start_to', 'Start to'], ['expiry_from', 'Expires from'], ['expiry_to', 'Expires to']] as const).map(([k, l]) => (
          <label key={k} className="flex items-center gap-1 text-sm">{l} <Input type="date" className="w-40" aria-label={l} value={u.value(k)} onChange={(e) => u.set(k, e.target.value)} /></label>))}
        {u.value('plan_id') && <Button variant="outline" size="sm" onClick={() => u.set('plan_id', '')}>Clear plan filter</Button>}
      </Toolbar>
      <QueryTable query={query} page={u.page} onPage={u.setPage} rowKey={(s) => s.id} emptyTitle="No subscriptions found" emptyDescription="Create a subscription or convert a confirmed quotation."
        columns={[
          { header: 'Number', cell: (s) => <Link className="font-medium text-primary hover:underline" to={`/subscriptions/${s.id}`}>{s.number}</Link> },
          { header: 'Customer', cell: (s) => <Link className="hover:underline" to={`/customers/${s.customer_id}`}>{s.customer_name}</Link> }, { header: 'Plan', cell: (s) => s.plan_name },
          { header: 'Frequency', cell: (s) => FREQUENCY_LABEL[s.billing_frequency] }, { header: 'Status', cell: (s) => <StatusBadge status={s.status} /> },
          { header: 'Next billing', cell: (s) => date(s.next_billing_date) }, { header: 'Total / period', cell: (s) => money(s.total) },
        ]} />
      <CreateDialog open={creating} onClose={() => setCreating(false)} />
    </PageContainer>
  )
}
