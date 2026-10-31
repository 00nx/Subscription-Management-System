import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery } from '@tanstack/react-query'
import { Controller, useForm } from 'react-hook-form'
import { z } from 'zod'
import { FormField, SelectField, TextAreaField } from '@/components/shared/FormField'
import { Button } from '@/components/ui/button'
import { useApiMutation } from '@/hooks/useApiMutation'
import { applyServerError, moneyField, required } from '@/lib/forms'
import { queryKeys } from '@/lib/queryKeys'
import { productService, taxService } from '@/services/catalog.service'
import type { Product } from '@/types'

const schema = z.object({
  name: required('Name'), product_type: required('Type'), sales_price: moneyField('Sales price'), cost_price: moneyField('Cost price'),
  tax_id: z.string(), extra_tax_ids: z.array(z.string()), status: z.enum(['ACTIVE', 'INACTIVE', 'ARCHIVED']), description: z.string(),
})
type Values = z.infer<typeof schema>

export function ProductForm({ product, readOnly, onSaved }: { product?: Product; readOnly?: boolean; onSaved?: (p: Product) => void }) {
  const taxes = useQuery({ queryKey: queryKeys.taxes.list({ all: true }), queryFn: () => taxService.list({ page_size: 100 }) })
  const { register, control, handleSubmit, setError, formState: { errors, isDirty } } = useForm<Values>({
    resolver: zodResolver(schema),
    values: { name: product?.name ?? '', product_type: product?.product_type ?? 'SERVICE', sales_price: product?.sales_price ?? '', cost_price: product?.cost_price ?? '0.00',
      tax_id: product?.tax_id ?? '', extra_tax_ids: product?.extra_tax_ids ?? [], status: product?.status ?? 'ACTIVE', description: product?.description ?? '' },
  })
  const save = useApiMutation((v: Values) => {
    const body = { ...v, tax_id: v.tax_id || null, description: v.description || null }
    return product ? productService.update(product.id, body) : productService.create(body)
  }, { invalidate: [queryKeys.products.all], success: product ? 'Product updated' : 'Product created', onSuccess: (p) => onSaved?.(p) })
  return (
    <form className="grid gap-4 sm:grid-cols-2" noValidate onSubmit={handleSubmit((v) => save.mutateAsync(v).catch((e) => applyServerError(e, setError)))}>
      <FormField label="Name" disabled={readOnly} error={errors.name?.message} {...register('name')} />
      <SelectField label="Type" disabled={readOnly} {...register('product_type')}>{['SERVICE', 'SOFTWARE', 'PHYSICAL', 'OTHER'].map((t) => <option key={t} value={t}>{t}</option>)}</SelectField>
      <FormField label="Sales price" inputMode="decimal" disabled={readOnly} error={errors.sales_price?.message} {...register('sales_price')} />
      <FormField label="Cost price" inputMode="decimal" disabled={readOnly} error={errors.cost_price?.message} {...register('cost_price')} />
      <SelectField label="Tax" disabled={readOnly} hint="Applied to invoice lines for this product." {...register('tax_id')}>
        <option value="">No tax</option>{taxes.data?.items.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.rate}%)</option>)}
      </SelectField>
      <Controller control={control} name="extra_tax_ids" render={({ field }) => (
        <fieldset className="space-y-1" disabled={readOnly}><legend className="text-sm font-medium">Additional taxes</legend>
          <div className="flex flex-wrap gap-x-3 gap-y-1">{taxes.data?.items.filter((t) => t.status === 'ACTIVE').map((t) => (
            <label key={t.id} className="flex items-center gap-1 text-xs"><input type="checkbox" checked={field.value.includes(t.id)}
              onChange={() => field.onChange(field.value.includes(t.id) ? field.value.filter((x) => x !== t.id) : [...field.value, t.id])} />{t.name} ({t.rate}%)</label>))}</div>
          <p className="text-xs text-muted-foreground">e.g. CGST + SGST: pick one above and the other here. Taxes that apply to all lines are added automatically.</p></fieldset>)} />
      <SelectField label="Status" disabled={readOnly} {...register('status')}><option value="ACTIVE">Active</option><option value="INACTIVE">Inactive</option><option value="ARCHIVED">Archived</option></SelectField>
      <div className="sm:col-span-2"><TextAreaField label="Description / notes" disabled={readOnly} {...register('description')} /></div>
      {errors.root && <p role="alert" className="text-sm text-destructive sm:col-span-2">{errors.root.message}</p>}
      {!readOnly && <div className="sm:col-span-2"><Button type="submit" disabled={save.isPending || (!!product && !isDirty)}>{product ? 'Save changes' : 'Create product'}</Button></div>}
    </form>
  )
}
