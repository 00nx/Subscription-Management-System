import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Controller, useFieldArray, useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { Plus, Send, Trash2 } from 'lucide-react'
import { PageContainer } from '@/components/layout/PageContainer'
import { CustomerPicker } from '@/components/shared/CustomerPicker'
import { FilterDropdown } from '@/components/shared/FilterDropdown'
import { FormField, TextAreaField } from '@/components/shared/FormField'
import { ConfirmationDialog } from '@/components/shared/ConfirmationDialog'
import { Modal } from '@/components/shared/Modal'
import { PageHeader } from '@/components/shared/PageHeader'
import { QueryTable } from '@/components/shared/QueryTable'
import { SearchInput } from '@/components/shared/SearchInput'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Toolbar } from '@/components/shared/Toolbar'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useApiMutation } from '@/hooks/useApiMutation'
import { useListQuery } from '@/hooks/useListQuery'
import { useUrlState } from '@/hooks/useUrlState'
import { date, label, money } from '@/lib/format'
import { applyServerError, intField, required } from '@/lib/forms'
import { queryKeys } from '@/lib/queryKeys'
import { taxService } from '@/services/catalog.service'
import { invoiceService } from '@/services/invoice.service'
import type { Invoice } from '@/types'

const schema = z.object({
  customer_id: required('Customer'), payment_terms_days: intField(0, 'Payment terms'), notes: z.string(),
  lines: z.array(z.object({ description: required('Description'), quantity: z.string().regex(/^[1-9]\d*$/, 'Whole number ≥ 1'), unit_price: z.string().regex(/^\d+(\.\d{1,2})?$/, 'Invalid amount'), tax_id: z.string() })).min(1, 'Add at least one line'),
})
type Values = z.infer<typeof schema>

function CreateInvoiceDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate()
  const taxes = useQuery({ queryKey: queryKeys.taxes.list({ all: true }), queryFn: () => taxService.list({ page_size: 100 }) })
  const { register, control, handleSubmit, reset, setError, formState: { errors } } = useForm<Values>({
    resolver: zodResolver(schema), defaultValues: { customer_id: '', payment_terms_days: '0', notes: '', lines: [{ description: '', quantity: '1', unit_price: '', tax_id: '' }] },
  })
  const { fields, append, remove } = useFieldArray({ control, name: 'lines' })
  const create = useApiMutation((v: Values) => invoiceService.create({ customer_id: v.customer_id, payment_terms_days: Number(v.payment_terms_days), notes: v.notes || null,
    lines: v.lines.map((l) => ({ description: l.description, quantity: Number(l.quantity), unit_price: l.unit_price, tax_id: l.tax_id || null })) }),
    { invalidate: [queryKeys.invoices.all], success: 'Invoice created as a draft', onSuccess: (i) => { reset(); onClose(); navigate(`/invoices/${i.id}`) } })
  return (
    <Modal open={open} onClose={onClose} wide title="New manual invoice" description="Recurring invoices are generated automatically. Use this for one-off charges.">
      <form className="space-y-4" noValidate onSubmit={handleSubmit((v) => create.mutateAsync(v).catch((e) => applyServerError(e, setError)))}>
        <Controller control={control} name="customer_id" render={({ field }) => <CustomerPicker value={field.value} onChange={field.onChange} error={errors.customer_id?.message} />} />
        <FormField label="Payment terms (days)" inputMode="numeric" error={errors.payment_terms_days?.message} {...register('payment_terms_days')} />
        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">Lines</legend>
          {fields.map((f, i) => (
            <div key={f.id} className="grid grid-cols-12 items-end gap-2">
              <label className="col-span-12 text-xs sm:col-span-5">Description<Input {...register(`lines.${i}.description`)} aria-invalid={!!errors.lines?.[i]?.description} /></label>
              <label className="col-span-3 text-xs sm:col-span-1">Qty<Input inputMode="numeric" {...register(`lines.${i}.quantity`)} /></label>
              <label className="col-span-4 text-xs sm:col-span-2">Unit price<Input inputMode="decimal" {...register(`lines.${i}.unit_price`)} aria-invalid={!!errors.lines?.[i]?.unit_price} /></label>
              <label className="col-span-4 text-xs sm:col-span-3">Tax
                <select className="h-9 w-full rounded-md border border-border bg-card px-2 text-sm" {...register(`lines.${i}.tax_id`)}><option value="">No tax</option>{taxes.data?.items.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.rate}%)</option>)}</select></label>
              <Button type="button" variant="ghost" size="icon" aria-label="Remove line" className="col-span-1" disabled={fields.length === 1} onClick={() => remove(i)}><Trash2 className="h-4 w-4" /></Button>
            </div>
          ))}
          {errors.lines && !Array.isArray(errors.lines) && <p className="text-sm text-destructive">{errors.lines.message}</p>}
          {errors.lines?.some?.((l) => l) && <p className="text-sm text-destructive">Check the highlighted line fields.</p>}
          <Button type="button" variant="outline" size="sm" onClick={() => append({ description: '', quantity: '1', unit_price: '', tax_id: '' })}><Plus className="h-4 w-4" aria-hidden />Add line</Button>
        </fieldset>
        <TextAreaField label="Notes" {...register('notes')} />
        {errors.root && <p role="alert" className="text-sm text-destructive">{errors.root.message}</p>}
        <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button type="submit" disabled={create.isPending}>Create draft invoice</Button></div>
      </form>
    </Modal>
  )
}

export const invoiceStatus = (i: Pick<Invoice, 'status' | 'is_overdue'>) => (i.is_overdue ? 'OVERDUE' : i.status)

export default function InvoicesPage() {
  const u = useUrlState()
  const [creating, setCreating] = useState(false)
  const params = { q: u.value('q'), status: u.value('status'), overdue: u.value('overdue') || undefined, date_from: u.value('from'), date_to: u.value('to'), page: u.page, sort: '-created_at' }
  const query = useListQuery(queryKeys.invoices.list, invoiceService.list, params)
  const [bulk, setBulk] = useState<boolean | null>(null) // null = closed, else "also send"
  const drafts = useQuery({ queryKey: [...queryKeys.invoices.all, 'drafts'], queryFn: () => invoiceService.list({ status: 'DRAFT', page_size: 100 }) })
  const draftIds = drafts.data?.items.map((i) => i.id) ?? []
  const run = useApiMutation((send: boolean) => invoiceService.bulkConfirm(draftIds, send), {
    invalidate: [queryKeys.invoices.all], success: (r) => `${r.confirmed} invoice(s) confirmed${r.sent ? `, ${r.sent} sent` : ''}${r.skipped.length ? `, ${r.skipped.length} skipped` : ''}`, onSuccess: () => setBulk(null),
  })
  return (
    <PageContainer>
      <PageHeader title="Invoices" description="Generated automatically from subscriptions, or created manually." actions={<>
        {draftIds.length > 0 && <Button variant="outline" onClick={() => setBulk(true)}><Send className="h-4 w-4" aria-hidden />Confirm &amp; send {draftIds.length} draft{draftIds.length > 1 ? 's' : ''}</Button>}
        <Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" aria-hidden />New invoice</Button></>} />
      <Toolbar>
        <SearchInput value={u.value('q')} onChange={(v) => u.set('q', v)} placeholder="Search INV-…" />
        <FilterDropdown label="Status" value={u.value('status')} onChange={(v) => u.set('status', v)} options={['DRAFT', 'CONFIRMED', 'PARTIALLY_PAID', 'PAID', 'CANCELLED'].map((s) => ({ label: label(s), value: s }))} />
        <FilterDropdown label="Overdue" value={u.value('overdue')} onChange={(v) => u.set('overdue', v)} options={[{ label: 'Overdue only', value: 'true' }, { label: 'Not overdue', value: 'false' }]} />
        <label className="flex items-center gap-1 text-sm">From <Input type="date" className="w-40" aria-label="Issued from" value={u.value('from')} onChange={(e) => u.set('from', e.target.value)} /></label>
        <label className="flex items-center gap-1 text-sm">To <Input type="date" className="w-40" aria-label="Issued to" value={u.value('to')} onChange={(e) => u.set('to', e.target.value)} /></label>
      </Toolbar>
      <QueryTable query={query} page={u.page} onPage={u.setPage} rowKey={(i) => i.id} emptyTitle="No invoices found" emptyDescription="Invoices appear when billing runs or when you create one."
        columns={[
          { header: 'Number', cell: (i) => <Link className="font-medium text-primary hover:underline" to={`/invoices/${i.id}`}>{i.number}</Link> }, { header: 'Customer', cell: (i) => i.customer_snapshot.name },
          { header: 'Status', cell: (i) => <StatusBadge status={invoiceStatus(i)} /> }, { header: 'Issued', cell: (i) => date(i.issue_date) }, { header: 'Due', cell: (i) => date(i.due_date) },
          { header: 'Total', cell: (i) => money(i.total, i.currency) }, { header: 'Outstanding', cell: (i) => money(i.outstanding, i.currency) },
        ]} />
      <ConfirmationDialog open={bulk !== null} title={`Confirm and send ${draftIds.length} draft invoice(s)?`} confirmLabel="Confirm & send"
        description="Each draft becomes a confirmed invoice, visible to the customer, and is emailed to them. Review the drafts first if unsure." onConfirm={() => run.mutate(true)} onCancel={() => setBulk(null)} />
      <CreateInvoiceDialog open={creating} onClose={() => setCreating(false)} />
    </PageContainer>
  )
}
