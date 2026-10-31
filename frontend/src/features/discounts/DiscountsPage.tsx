import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
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
import { date, money } from '@/lib/format'
import { applyServerError, intField, moneyField, optionalInt, required } from '@/lib/forms'
import { queryKeys } from '@/lib/queryKeys'
import { discountService, productService } from '@/services/catalog.service'
import type { Discount } from '@/types'

const schema = z.object({
  name: required('Name'), description: z.string(), discount_type: z.enum(['FIXED', 'PERCENTAGE']),
  value: moneyField('Value').refine((v) => Number(v) > 0, 'Value must be greater than zero'),
  min_purchase_amount: moneyField('Minimum purchase'), min_quantity: intField(0, 'Minimum quantity'), start_date: z.string(), end_date: z.string(),
  max_usage: optionalInt, is_active: z.boolean(), product_ids: z.array(z.string()),
}).refine((v) => v.discount_type !== 'PERCENTAGE' || Number(v.value) <= 100, { path: ['value'], message: 'A percentage cannot exceed 100' })
  .refine((v) => !v.start_date || !v.end_date || v.end_date >= v.start_date, { path: ['end_date'], message: 'End date must not be before the start date' })
type Values = z.infer<typeof schema>

function DiscountDialog({ discount, open, onClose }: { discount: Discount | null; open: boolean; onClose: () => void }) {
  const products = useQuery({ queryKey: queryKeys.products.list({ all: true }), queryFn: () => productService.list({ page_size: 100 }) })
  const { register, control, handleSubmit, reset, setError, formState: { errors } } = useForm<Values>({
    resolver: zodResolver(schema),
    values: {
      name: discount?.name ?? '', description: discount?.description ?? '', discount_type: discount?.discount_type ?? 'PERCENTAGE', value: discount?.value ?? '',
      min_purchase_amount: discount?.min_purchase_amount ?? '0.00', min_quantity: String(discount?.min_quantity ?? 0), start_date: discount?.start_date ?? '', end_date: discount?.end_date ?? '',
      max_usage: discount?.max_usage != null ? String(discount.max_usage) : '', is_active: discount?.is_active ?? true, product_ids: discount?.product_ids ?? [],
    },
  })
  const save = useApiMutation((v: Values) => {
    const body = { ...v, min_quantity: Number(v.min_quantity), start_date: v.start_date || null, end_date: v.end_date || null, max_usage: v.max_usage ? Number(v.max_usage) : null, description: v.description || null }
    return discount ? discountService.update(discount.id, body) : discountService.create(body)
  }, { invalidate: [queryKeys.discounts.all], success: discount ? 'Discount updated' : 'Discount created', onSuccess: () => { reset(); onClose() } })
  return (
    <Modal open={open} onClose={onClose} wide title={discount ? 'Edit discount' : 'New discount'}
      description="A discount applies to the next eligible invoice of subscriptions containing the chosen products, or of subscriptions it is explicitly attached to.">
      <form className="grid gap-4 sm:grid-cols-2" noValidate onSubmit={handleSubmit((v) => save.mutateAsync(v).catch((e) => applyServerError(e, setError)))}>
        <FormField label="Name" error={errors.name?.message} {...register('name')} />
        <SelectField label="Type" {...register('discount_type')}><option value="PERCENTAGE">Percentage</option><option value="FIXED">Fixed amount</option></SelectField>
        <FormField label="Value" inputMode="decimal" error={errors.value?.message} {...register('value')} />
        <FormField label="Maximum uses" inputMode="numeric" hint="Leave empty for unlimited." error={errors.max_usage?.message} {...register('max_usage')} />
        <FormField label="Minimum purchase amount" inputMode="decimal" error={errors.min_purchase_amount?.message} {...register('min_purchase_amount')} />
        <FormField label="Minimum quantity" inputMode="numeric" error={errors.min_quantity?.message} {...register('min_quantity')} />
        <FormField label="Start date" type="date" {...register('start_date')} />
        <FormField label="End date" type="date" error={errors.end_date?.message} {...register('end_date')} />
        <div className="sm:col-span-2"><TextAreaField label="Description" {...register('description')} /></div>
        <div className="sm:col-span-2">
          <Controller control={control} name="product_ids" render={({ field }) => (
            <MultiCheck legend="Applicable products" value={field.value} onChange={field.onChange} options={(products.data?.items ?? []).map((p) => ({ value: p.id, label: p.name }))} />)} />
        </div>
        <div className="sm:col-span-2"><CheckboxField label="Active" {...register('is_active')} /></div>
        {errors.root && <p role="alert" className="text-sm text-destructive sm:col-span-2">{errors.root.message}</p>}
        <div className="flex justify-end gap-2 sm:col-span-2"><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button type="submit" disabled={save.isPending}>Save discount</Button></div>
      </form>
    </Modal>
  )
}

export default function DiscountsPage() {
  const { user } = useAuth()
  const admin = user?.role === 'ADMIN'
  const u = useUrlState()
  const [dialog, setDialog] = useState<{ discount: Discount | null } | null>(null)
  const query = useListQuery(queryKeys.discounts.list, discountService.list, { q: u.value('q'), is_active: u.value('active'), page: u.page })
  const toggle = useApiMutation((d: Discount) => discountService.update(d.id, { is_active: !d.is_active }), { invalidate: [queryKeys.discounts.all], success: 'Discount updated' })
  return (
    <PageContainer>
      <PageHeader title="Discounts" description="Percentage and fixed-amount discount rules."
        actions={admin ? <Button onClick={() => setDialog({ discount: null })}><Plus className="h-4 w-4" aria-hidden />New discount</Button> : undefined} />
      <Toolbar>
        <SearchInput value={u.value('q')} onChange={(v) => u.set('q', v)} placeholder="Search discounts" />
        <FilterDropdown label="Status" value={u.value('active')} onChange={(v) => u.set('active', v)} options={[{ label: 'Active', value: 'true' }, { label: 'Inactive', value: 'false' }]} />
      </Toolbar>
      <QueryTable query={query} page={u.page} onPage={u.setPage} rowKey={(d) => d.id} emptyTitle="No discounts yet" emptyDescription="Discount rules apply automatically when invoices are generated."
        columns={[
          { header: 'Name', cell: (d) => d.name }, { header: 'Value', cell: (d) => (d.discount_type === 'PERCENTAGE' ? `${d.value}%` : money(d.value)) },
          { header: 'Valid', cell: (d) => (d.start_date || d.end_date ? `${date(d.start_date)} → ${date(d.end_date)}` : 'Always') },
          { header: 'Usage', cell: (d) => `${d.usage_count}${d.max_usage != null ? ` / ${d.max_usage}` : ''}` }, { header: 'Status', cell: (d) => <StatusBadge status={d.end_date && d.end_date < new Date().toISOString().slice(0, 10) ? 'EXPIRED' : d.is_active ? 'active' : 'inactive'} /> },
          { header: '', cell: (d) => admin ? <div className="flex gap-2"><Button variant="outline" size="sm" onClick={() => setDialog({ discount: d })}>Edit</Button><Button variant="ghost" size="sm" onClick={() => toggle.mutate(d)}>{d.is_active ? 'Deactivate' : 'Activate'}</Button></div> : null },
        ]} />
      <DiscountDialog discount={dialog?.discount ?? null} open={!!dialog} onClose={() => setDialog(null)} />
    </PageContainer>
  )
}
