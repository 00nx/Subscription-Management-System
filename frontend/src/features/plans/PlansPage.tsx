import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'
import { z } from 'zod'
import { Plus } from 'lucide-react'
import { PageContainer } from '@/components/layout/PageContainer'
import { FilterDropdown } from '@/components/shared/FilterDropdown'
import { CheckboxField, FormField, SelectField, TextAreaField } from '@/components/shared/FormField'
import { Modal } from '@/components/shared/Modal'
import { MultiCheck } from '@/components/shared/MultiCheck'
import { PageHeader } from '@/components/shared/PageHeader'
import { QueryTable } from '@/components/shared/QueryTable'
import { SearchInput } from '@/components/shared/SearchInput'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Toolbar } from '@/components/shared/Toolbar'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/hooks/useAuth'
import { useApiMutation } from '@/hooks/useApiMutation'
import { useListQuery } from '@/hooks/useListQuery'
import { useUrlState } from '@/hooks/useUrlState'
import { date, FREQUENCY_LABEL, money } from '@/lib/format'
import { applyServerError, intField, moneyField, required } from '@/lib/forms'
import { queryKeys } from '@/lib/queryKeys'
import { planService, productService } from '@/services/catalog.service'
import type { Plan } from '@/types'

const schema = z.object({
  name: required('Name'), description: z.string(), product_id: required('Product'), price: moneyField('Price'),
  billing_frequency: z.enum(['DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY']), min_quantity: intField(1, 'Minimum quantity'),
  available_from: z.string(), available_until: z.string(), auto_close: z.boolean(), allow_early_closure: z.boolean(), allow_pause: z.boolean(), allow_renewal: z.boolean(),
  status: z.enum(['ACTIVE', 'INACTIVE', 'ARCHIVED']), extra_product_ids: z.array(z.string()),
})
type Values = z.infer<typeof schema>

function PlanDialog({ plan, open, onClose }: { plan: Plan | null; open: boolean; onClose: () => void }) {
  const products = useQuery({ queryKey: queryKeys.products.list({ status: 'ACTIVE', all: true }), queryFn: () => productService.list({ status: 'ACTIVE', page_size: 100 }) })
  const { register, control, handleSubmit, reset, watch, setError, formState: { errors } } = useForm<Values>({
    resolver: zodResolver(schema),
    values: {
      name: plan?.name ?? '', description: plan?.description ?? '', product_id: plan?.product_id ?? '', price: plan?.price ?? '', billing_frequency: plan?.billing_frequency ?? 'MONTHLY',
      min_quantity: String(plan?.min_quantity ?? 1), available_from: plan?.available_from ?? '', available_until: plan?.available_until ?? '', auto_close: plan?.auto_close ?? true,
      allow_early_closure: plan?.allow_early_closure ?? true, allow_pause: plan?.allow_pause ?? true, allow_renewal: plan?.allow_renewal ?? true, status: plan?.status ?? 'ACTIVE',
      extra_product_ids: plan?.extra_product_ids ?? [],
    },
  })
  const save = useApiMutation((v: Values) => {
    const body = { ...v, min_quantity: Number(v.min_quantity), available_from: v.available_from || null, available_until: v.available_until || null, description: v.description || null }
    return plan ? planService.update(plan.id, body) : planService.create(body)
  }, { invalidate: [queryKeys.plans.all], success: plan ? 'Plan updated' : 'Plan created', onSuccess: () => { reset(); onClose() } })
  const main = watch('product_id')
  return (
    <Modal open={open} onClose={onClose} wide title={plan ? 'Edit plan' : 'New plan'} description="Editing a plan never changes existing subscriptions: they keep the price and frequency they started with.">
      <form className="grid gap-4 sm:grid-cols-2" noValidate onSubmit={handleSubmit((v) => save.mutateAsync(v).catch((e) => applyServerError(e, setError)))}>
        <FormField label="Plan name" error={errors.name?.message} {...register('name')} />
        <SelectField label="Product" error={errors.product_id?.message} {...register('product_id')}><option value="">Select a product…</option>{products.data?.items.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</SelectField>
        <FormField label="Price per period" inputMode="decimal" error={errors.price?.message} {...register('price')} />
        <SelectField label="Billing frequency" {...register('billing_frequency')}>{Object.entries(FREQUENCY_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</SelectField>
        <FormField label="Minimum quantity" inputMode="numeric" error={errors.min_quantity?.message} {...register('min_quantity')} />
        <SelectField label="Status" {...register('status')}><option value="ACTIVE">Active</option><option value="INACTIVE">Inactive</option><option value="ARCHIVED">Archived</option></SelectField>
        <FormField label="Available from" type="date" {...register('available_from')} />
        <FormField label="Available until" type="date" {...register('available_until')} />
        <div className="sm:col-span-2"><TextAreaField label="Description" {...register('description')} /></div>
        <div className="grid gap-2 sm:col-span-2 sm:grid-cols-2">
          <CheckboxField label="Auto-close when the term ends" {...register('auto_close')} />
          <CheckboxField label="Allow early closure" {...register('allow_early_closure')} />
          <CheckboxField label="Allow pausing" {...register('allow_pause')} />
          <CheckboxField label="Allow renewal" {...register('allow_renewal')} />
        </div>
        <div className="sm:col-span-2">
          <Controller control={control} name="extra_product_ids" render={({ field }) => (
            <MultiCheck legend="Additional products allowed on this plan" value={field.value} onChange={field.onChange} empty="No other products."
              options={(products.data?.items ?? []).filter((p) => p.id !== main).map((p) => ({ value: p.id, label: p.name }))} />)} />
        </div>
        {errors.root && <p role="alert" className="text-sm text-destructive sm:col-span-2">{errors.root.message}</p>}
        <div className="flex justify-end gap-2 sm:col-span-2"><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button type="submit" disabled={save.isPending}>Save plan</Button></div>
      </form>
    </Modal>
  )
}

export default function PlansPage() {
  const { user } = useAuth()
  const admin = user?.role === 'ADMIN'
  const u = useUrlState()
  const [dialog, setDialog] = useState<{ plan: Plan | null } | null>(null)
  const params = { q: u.value('q'), status: u.value('status'), billing_frequency: u.value('frequency'), page: u.page }
  const query = useListQuery(queryKeys.plans.list, planService.list, params)
  const setStatus = useApiMutation((v: { id: string; status: string }) => planService.update(v.id, { status: v.status }), { invalidate: [queryKeys.plans.all], success: 'Plan status updated' })
  return (
    <PageContainer>
      <PageHeader title="Plans" description="Subscription plans: price, billing frequency and rules."
        actions={admin ? <Button onClick={() => setDialog({ plan: null })}><Plus className="h-4 w-4" aria-hidden />New plan</Button> : undefined} />
      <Toolbar>
        <SearchInput value={u.value('q')} onChange={(v) => u.set('q', v)} placeholder="Search plans" />
        <FilterDropdown label="Status" value={u.value('status')} onChange={(v) => u.set('status', v)} options={['ACTIVE', 'INACTIVE', 'ARCHIVED'].map((s) => ({ label: s, value: s }))} />
        <FilterDropdown label="Frequency" value={u.value('frequency')} onChange={(v) => u.set('frequency', v)} options={Object.entries(FREQUENCY_LABEL).map(([value, label]) => ({ label, value }))} />
      </Toolbar>
      <QueryTable query={query} page={u.page} onPage={u.setPage} rowKey={(p) => p.id} emptyTitle="No plans yet" emptyDescription="Create a plan to start selling subscriptions."
        columns={[
          { header: 'Plan', cell: (p) => p.name }, { header: 'Price', cell: (p) => money(p.price) }, { header: 'Frequency', cell: (p) => FREQUENCY_LABEL[p.billing_frequency] },
          { header: 'Availability', cell: (p) => (p.available_from || p.available_until ? `${date(p.available_from)} → ${date(p.available_until)}` : 'Always') },
          { header: 'Status', cell: (p) => <StatusBadge status={p.available_until && p.available_until < new Date().toISOString().slice(0, 10) ? 'EXPIRED' : p.status} /> },
          { header: '', cell: (p) => (
            <div className="flex gap-2">
              <Button asChild variant="ghost" size="sm"><Link to={`/subscriptions?plan_id=${p.id}`}>Subscriptions</Link></Button>
              {admin && <>
                <Button variant="outline" size="sm" onClick={() => setDialog({ plan: p })}>Edit</Button>
                <Button variant="outline" size="sm" onClick={() => setStatus.mutate({ id: p.id, status: p.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE' })}>{p.status === 'ACTIVE' ? 'Deactivate' : 'Activate'}</Button>
                {p.status !== 'ARCHIVED' && <Button variant="ghost" size="sm" onClick={() => setStatus.mutate({ id: p.id, status: 'ARCHIVED' })}>Archive</Button>}
              </>}
            </div>) },
        ]} />
      <PlanDialog plan={dialog?.plan ?? null} open={!!dialog} onClose={() => setDialog(null)} />
    </PageContainer>
  )
}
