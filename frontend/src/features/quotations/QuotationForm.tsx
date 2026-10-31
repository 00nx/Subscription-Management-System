import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery } from '@tanstack/react-query'
import { Controller, useForm } from 'react-hook-form'
import { z } from 'zod'
import { CustomerPicker } from '@/components/shared/CustomerPicker'
import { FormField, SelectField, TextAreaField } from '@/components/shared/FormField'
import { LinesEditor, toLineInputs, type LineValues } from '@/components/shared/LinesEditor'
import { Button } from '@/components/ui/button'
import { useApiMutation } from '@/hooks/useApiMutation'
import { applyServerError, intField, optionalInt } from '@/lib/forms'
import { money } from '@/lib/format'
import { queryKeys } from '@/lib/queryKeys'
import { discountService, planService, productService } from '@/services/catalog.service'
import { quotationService } from '@/services/sales.service'
import type { Quotation } from '@/types'

const schema = z.object({
  customer_id: z.string().min(1, 'Choose a customer'), template_id: z.string(), plan_id: z.string(), discount_id: z.string(), validity_days: optionalInt,
  payment_terms_days: intField(0, 'Payment terms'), notes: z.string(),
  lines: z.array(z.object({ product_id: z.string(), variant_ids: z.array(z.string()), quantity: z.string().regex(/^\d+$/, 'Whole number'), unit_price: z.string().regex(/^(\d+(\.\d{1,2})?)?$/, 'Invalid amount') })),
})
type Values = z.infer<typeof schema>

export function QuotationForm({ quotation, onSaved }: { quotation?: Quotation; onSaved: (q: Quotation) => void }) {
  const plans = useQuery({ queryKey: queryKeys.plans.list({ active: true }), queryFn: () => planService.list({ status: 'ACTIVE', page_size: 100 }) })
  const products = useQuery({ queryKey: queryKeys.products.list({ all: true }), queryFn: () => productService.list({ status: 'ACTIVE', page_size: 100 }) })
  const discounts = useQuery({ queryKey: queryKeys.discounts.list({ active: true }), queryFn: () => discountService.list({ is_active: 'true', page_size: 100 }) })
  const templates = useQuery({ queryKey: queryKeys.templates.list({ all: true }), queryFn: () => quotationService.templates({ page_size: 100 }) })
  const { register, control, handleSubmit, watch, setError, formState: { errors } } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      customer_id: quotation?.customer_id ?? '', template_id: quotation?.template_id ?? '', plan_id: quotation?.plan_id ?? '', discount_id: quotation?.discount_id ?? '', validity_days: '',
      payment_terms_days: String(quotation?.payment_terms_days ?? 0), notes: quotation?.notes ?? '',
      lines: (quotation?.lines ?? []).map((l): LineValues => ({ product_id: l.product_id, variant_ids: l.variants?.map((v) => v.id) ?? (l.variant_id ? [l.variant_id] : []), quantity: String(l.quantity), unit_price: l.unit_price })),
    },
  })
  const planId = watch('plan_id') || templates.data?.items.find((t) => t.id === watch('template_id'))?.plan_id || ''
  const plan = plans.data?.items.find((p) => p.id === planId)
  const allowed = (products.data?.items ?? []).filter((p) => !plan || p.id === plan.product_id || plan.extra_product_ids.includes(p.id))
  const save = useApiMutation((v: Values) => {
    const lines = toLineInputs(v.lines as LineValues[])
    if (quotation) return quotationService.update(quotation.id, { plan_id: v.plan_id || undefined, discount_id: v.discount_id || null, validity_days: v.validity_days ? Number(v.validity_days) : undefined, payment_terms_days: Number(v.payment_terms_days), notes: v.notes || null, lines })
    return quotationService.create({ customer_id: v.customer_id, template_id: v.template_id || undefined, plan_id: v.plan_id || undefined, discount_id: v.discount_id || undefined, validity_days: v.validity_days ? Number(v.validity_days) : undefined, payment_terms_days: Number(v.payment_terms_days), notes: v.notes || undefined, lines })
  }, { invalidate: [queryKeys.quotations.all], success: quotation ? 'Quotation updated' : 'Quotation created', onSuccess: onSaved })

  return (
    <form className="grid gap-4 sm:grid-cols-2" noValidate onSubmit={handleSubmit((v) => save.mutateAsync(v).catch((e) => applyServerError(e, setError)))}>
      <div className="sm:col-span-2">
        {quotation ? <p className="text-sm">Customer: <strong>{quotation.customer_name}</strong></p> : <Controller control={control} name="customer_id" render={({ field }) => <CustomerPicker value={field.value} onChange={field.onChange} error={errors.customer_id?.message} />} />}
      </div>
      {!quotation && <SelectField label="Template" hint="Pre-fills plan, lines, validity and terms." {...register('template_id')}><option value="">No template</option>{templates.data?.items.filter((t) => t.status === 'ACTIVE').map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</SelectField>}
      <SelectField label="Plan" error={errors.plan_id?.message} {...register('plan_id')}><option value="">Use template's plan…</option>{plans.data?.items.filter((p) => p.is_available).map((p) => <option key={p.id} value={p.id}>{p.name} · {money(p.price)}</option>)}</SelectField>
      <SelectField label="Discount" hint="Estimated on the quotation; applied for real when invoices are generated." {...register('discount_id')}><option value="">No discount</option>{discounts.data?.items.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</SelectField>
      <FormField label="Valid for (days)" inputMode="numeric" hint="Default: template or 30 days." error={errors.validity_days?.message} {...register('validity_days')} />
      <FormField label="Payment terms (days)" inputMode="numeric" error={errors.payment_terms_days?.message} {...register('payment_terms_days')} />
      <div className="sm:col-span-2"><LinesEditor control={control} register={register} products={allowed} /></div>
      <div className="sm:col-span-2"><TextAreaField label="Notes and terms" {...register('notes')} /></div>
      {errors.root && <p role="alert" className="text-sm text-destructive sm:col-span-2">{errors.root.message}</p>}
      <div className="sm:col-span-2"><Button type="submit" disabled={save.isPending}>{quotation ? 'Save quotation' : 'Create quotation'}</Button></div>
    </form>
  )
}
