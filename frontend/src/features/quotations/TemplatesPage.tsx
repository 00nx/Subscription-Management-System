import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { Plus } from 'lucide-react'
import { PageContainer } from '@/components/layout/PageContainer'
import { FormField, SelectField, TextAreaField } from '@/components/shared/FormField'
import { LinesEditor, toLineInputs, type LineValues } from '@/components/shared/LinesEditor'
import { Modal } from '@/components/shared/Modal'
import { PageHeader } from '@/components/shared/PageHeader'
import { QueryTable } from '@/components/shared/QueryTable'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Button } from '@/components/ui/button'
import { useApiMutation } from '@/hooks/useApiMutation'
import { useListQuery } from '@/hooks/useListQuery'
import { applyServerError, intField, required } from '@/lib/forms'
import { queryKeys } from '@/lib/queryKeys'
import { planService, productService, discountService } from '@/services/catalog.service'
import { quotationService } from '@/services/sales.service'
import type { QuotationTemplate } from '@/types'

const schema = z.object({
  name: required('Name'), plan_id: z.string(), discount_id: z.string(), validity_days: intField(1, 'Validity'), payment_terms_days: intField(0, 'Payment terms'), notes: z.string(), terms: z.string(), status: z.enum(['ACTIVE', 'INACTIVE']),
  lines: z.array(z.object({ product_id: z.string(), variant_ids: z.array(z.string()), quantity: z.string().regex(/^\d+$/, 'Whole number'), unit_price: z.string().regex(/^(\d+(\.\d{1,2})?)?$/, 'Invalid amount') })),
})
type Values = z.infer<typeof schema>

function TemplateDialog({ template, open, onClose }: { template: QuotationTemplate | null; open: boolean; onClose: () => void }) {
  const plans = useQuery({ queryKey: queryKeys.plans.list({ active: true }), queryFn: () => planService.list({ status: 'ACTIVE', page_size: 100 }) })
  const discounts = useQuery({ queryKey: queryKeys.discounts.list({ active: true }), queryFn: () => discountService.list({ is_active: 'true', page_size: 100 }) })
  const products = useQuery({ queryKey: queryKeys.products.list({ all: true }), queryFn: () => productService.list({ status: 'ACTIVE', page_size: 100 }) })
  const { register, control, handleSubmit, reset, setError, formState: { errors } } = useForm<Values>({
    resolver: zodResolver(schema),
    values: {
      name: template?.name ?? '', plan_id: template?.plan_id ?? '', discount_id: template?.discount_id ?? '', validity_days: String(template?.validity_days ?? 30), payment_terms_days: String(template?.payment_terms_days ?? 0), notes: template?.notes ?? '', terms: template?.terms ?? '',
      status: (template?.status === 'INACTIVE' ? 'INACTIVE' : 'ACTIVE'), lines: (template?.lines ?? []).map((l): LineValues => ({ product_id: l.product_id, variant_ids: l.variant_ids?.length ? l.variant_ids : l.variant_id ? [l.variant_id] : [], quantity: String(l.quantity), unit_price: l.unit_price ?? '' })),
    },
  })
  const save = useApiMutation((v: Values) => {
    const body = { name: v.name, plan_id: v.plan_id || null, discount_id: v.discount_id || null, validity_days: Number(v.validity_days), payment_terms_days: Number(v.payment_terms_days), notes: v.notes || null, terms: v.terms || null, status: v.status, lines: toLineInputs(v.lines as LineValues[]) }
    return template ? quotationService.updateTemplate(template.id, body) : quotationService.createTemplate(body)
  }, { invalidate: [queryKeys.templates.all], success: template ? 'Template updated' : 'Template created', onSuccess: () => { reset(); onClose() } })
  return (
    <Modal open={open} onClose={onClose} wide title={template ? 'Edit template' : 'New template'} description="Templates pre-fill new quotations: plan, lines, validity, payment terms and notes.">
      <form className="grid gap-4 sm:grid-cols-2" noValidate onSubmit={handleSubmit((v) => save.mutateAsync(v).catch((e) => applyServerError(e, setError)))}>
        <FormField label="Template name" error={errors.name?.message} {...register('name')} />
        <SelectField label="Plan" {...register('plan_id')}><option value="">None</option>{plans.data?.items.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</SelectField>
        <SelectField label="Default discount" hint="Pre-selected on quotations made from this template." {...register('discount_id')}><option value="">None</option>{discounts.data?.items.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</SelectField>
        <FormField label="Validity (days)" inputMode="numeric" error={errors.validity_days?.message} {...register('validity_days')} />
        <FormField label="Payment terms (days)" inputMode="numeric" error={errors.payment_terms_days?.message} {...register('payment_terms_days')} />
        <div className="sm:col-span-2"><LinesEditor control={control} register={register} products={products.data?.items ?? []} /></div>
        <div className="sm:col-span-2"><TextAreaField label="Notes" {...register('notes')} /></div>
        <div className="sm:col-span-2"><TextAreaField label="Terms" {...register('terms')} /></div>
        <SelectField label="Status" {...register('status')}><option value="ACTIVE">Active</option><option value="INACTIVE">Inactive</option></SelectField>
        {errors.root && <p role="alert" className="text-sm text-destructive sm:col-span-2">{errors.root.message}</p>}
        <div className="flex justify-end gap-2 sm:col-span-2"><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button type="submit" disabled={save.isPending}>Save template</Button></div>
      </form>
    </Modal>
  )
}

export default function TemplatesPage() {
  const [dialog, setDialog] = useState<{ t: QuotationTemplate | null } | null>(null)
  const query = useListQuery(queryKeys.templates.list, quotationService.templates, { page_size: 50 })
  return (
    <PageContainer>
      <PageHeader title="Quotation templates" description="Reusable starting points for quotations." actions={<Button onClick={() => setDialog({ t: null })}><Plus className="h-4 w-4" aria-hidden />New template</Button>} />
      <QueryTable query={query} page={1} onPage={() => undefined} rowKey={(t) => t.id} emptyTitle="No templates yet" emptyDescription="Create a template to speed up quotation entry."
        columns={[{ header: 'Name', cell: (t) => t.name }, { header: 'Validity', cell: (t) => `${t.validity_days} days` }, { header: 'Lines', cell: (t) => t.lines.length }, { header: 'Status', cell: (t) => <StatusBadge status={t.status} /> },
          { header: '', cell: (t) => <Button size="sm" variant="outline" onClick={() => setDialog({ t })}>Edit</Button> }]} />
      <TemplateDialog template={dialog?.t ?? null} open={!!dialog} onClose={() => setDialog(null)} />
    </PageContainer>
  )
}
