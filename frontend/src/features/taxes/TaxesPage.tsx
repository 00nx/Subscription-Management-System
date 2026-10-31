import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { Plus } from 'lucide-react'
import { PageContainer } from '@/components/layout/PageContainer'
import { FormField, SelectField } from '@/components/shared/FormField'
import { Modal } from '@/components/shared/Modal'
import { PageHeader } from '@/components/shared/PageHeader'
import { QueryTable } from '@/components/shared/QueryTable'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/hooks/useAuth'
import { useApiMutation } from '@/hooks/useApiMutation'
import { useListQuery } from '@/hooks/useListQuery'
import { applyServerError, required } from '@/lib/forms'
import { queryKeys } from '@/lib/queryKeys'
import { taxService } from '@/services/catalog.service'
import type { RecordStatus, Tax } from '@/types'

const schema = z.object({
  name: required('Name'),
  rate: z.string().regex(/^\d+(\.\d{1,2})?$/, 'Enter a rate like 18 or 12.5').refine((v) => Number(v) <= 100, 'A rate cannot exceed 100'),
  description: z.string(), applies_to: z.enum(['PRODUCTS', 'ALL']), status: z.enum(['ACTIVE', 'INACTIVE', 'ARCHIVED']),
})
type Values = z.infer<typeof schema>

function TaxDialog({ tax, open, onClose }: { tax: Tax | null; open: boolean; onClose: () => void }) {
  const { register, handleSubmit, reset, setError, formState: { errors } } = useForm<Values>({
    resolver: zodResolver(schema), values: { name: tax?.name ?? '', rate: tax?.rate ?? '', description: tax?.description ?? '', applies_to: tax?.applies_to ?? 'PRODUCTS', status: (tax?.status ?? 'ACTIVE') as RecordStatus },
  })
  const save = useApiMutation((v: Values) => (tax ? taxService.update(tax.id, v) : taxService.create(v)), {
    invalidate: [queryKeys.taxes.all], success: tax ? 'Tax updated' : 'Tax created', onSuccess: () => { reset(); onClose() },
  })
  return (
    <Modal open={open} onClose={onClose} title={tax ? 'Edit tax' : 'New tax'} description="Rate changes apply to future invoices only; issued invoices keep their own rate.">
      <form className="space-y-4" noValidate onSubmit={handleSubmit((v) => save.mutateAsync(v).catch((e) => applyServerError(e, setError)))}>
        <FormField label="Name" error={errors.name?.message} {...register('name')} />
        <FormField label="Rate (%)" inputMode="decimal" error={errors.rate?.message} {...register('rate')} />
        <FormField label="Description" {...register('description')} />
        <SelectField label="Applies to" hint="'All lines' adds this tax to every invoice line automatically." {...register('applies_to')}><option value="PRODUCTS">Products that select it</option><option value="ALL">All lines</option></SelectField>
        <SelectField label="Status" {...register('status')}><option value="ACTIVE">Active</option><option value="INACTIVE">Inactive</option></SelectField>
        {errors.root && <p role="alert" className="text-sm text-destructive">{errors.root.message}</p>}
        <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button type="submit" disabled={save.isPending}>Save</Button></div>
      </form>
    </Modal>
  )
}


export default function TaxesPage() {
  const { user } = useAuth()
  const admin = user?.role === 'ADMIN'
  const [dialog, setDialog] = useState<{ tax: Tax | null } | null>(null)
  const taxes = useListQuery(queryKeys.taxes.list, taxService.list, { page_size: 100 })
  return (
    <PageContainer>
      <PageHeader title="Taxes" description="GST and other tax rates. Assign them to products; issued invoices keep the rate they were issued with."
        actions={admin ? <Button onClick={() => setDialog({ tax: null })}><Plus className="h-4 w-4" aria-hidden />New tax</Button> : undefined} />
      <QueryTable query={taxes} page={1} onPage={() => undefined} rowKey={(t) => t.id} emptyTitle="No taxes configured" emptyDescription="Create a tax, then assign it to products." columns={[
        { header: 'Name', cell: (t) => t.name }, { header: 'Rate', cell: (t) => `${t.rate}%` }, { header: 'Applies to', cell: (t) => (t.applies_to === 'ALL' ? 'All lines' : 'Selected products') },
        { header: 'Description', cell: (t) => t.description ?? '-' }, { header: 'Status', cell: (t) => <StatusBadge status={t.status} /> },
        { header: '', cell: (t) => admin ? <Button variant="outline" size="sm" onClick={() => setDialog({ tax: t })}>Edit</Button> : null }]} />
      <TaxDialog tax={dialog?.tax ?? null} open={!!dialog} onClose={() => setDialog(null)} />
    </PageContainer>
  )
}
