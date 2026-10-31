import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate, useParams } from 'react-router-dom'
import { z } from 'zod'
import { Plus } from 'lucide-react'
import { PageContainer } from '@/components/layout/PageContainer'
import { ConfirmationDialog } from '@/components/shared/ConfirmationDialog'
import { DataTable } from '@/components/shared/DataTable'
import { ErrorState } from '@/components/shared/ErrorState'
import { FormField, SelectField } from '@/components/shared/FormField'
import { LoadingState } from '@/components/shared/LoadingState'
import { Modal } from '@/components/shared/Modal'
import { PageHeader } from '@/components/shared/PageHeader'
import { Section } from '@/components/shared/Section'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/hooks/useAuth'
import { useApiMutation } from '@/hooks/useApiMutation'
import { money } from '@/lib/format'
import { applyServerError, moneyField, required } from '@/lib/forms'
import { queryKeys } from '@/lib/queryKeys'
import { productService } from '@/services/catalog.service'
import type { Product, Variant } from '@/types'
import { ProductForm } from './ProductForm'

const vSchema = z.object({ name: required('Name'), attribute_name: required('Attribute'), attribute_value: required('Value'), additional_price: moneyField('Additional price'), status: z.enum(['ACTIVE', 'INACTIVE', 'ARCHIVED']) })
type VValues = z.infer<typeof vSchema>

function VariantDialog({ product, variant, open, onClose }: { product: Product; variant: Variant | null; open: boolean; onClose: () => void }) {
  const { register, handleSubmit, reset, setError, formState: { errors } } = useForm<VValues>({
    resolver: zodResolver(vSchema),
    values: { name: variant?.name ?? '', attribute_name: variant?.attribute_name ?? 'Brand', attribute_value: variant?.attribute_value ?? '', additional_price: variant?.additional_price ?? '0.00', status: variant?.status ?? 'ACTIVE' },
  })
  const save = useApiMutation((v: VValues) => (variant ? productService.updateVariant(product.id, variant.id, v) : productService.createVariant(product.id, v)),
    { invalidate: [queryKeys.products.all], success: variant ? 'Variant updated' : 'Variant added', onSuccess: () => { reset(); onClose() } })
  return (
    <Modal open={open} onClose={onClose} title={variant ? 'Edit variant' : 'Add variant'} description={`The additional price is added to ${product.name}'s price.`}>
      <form className="space-y-4" noValidate onSubmit={handleSubmit((v) => save.mutateAsync(v).catch((e) => applyServerError(e, setError)))}>
        <FormField label="Variant name" error={errors.name?.message} {...register('name')} />
        <div className="grid grid-cols-2 gap-3">
          <FormField label="Attribute" error={errors.attribute_name?.message} {...register('attribute_name')} />
          <FormField label="Value" error={errors.attribute_value?.message} {...register('attribute_value')} />
        </div>
        <FormField label="Additional price" inputMode="decimal" error={errors.additional_price?.message} {...register('additional_price')} />
        <SelectField label="Status" {...register('status')}><option value="ACTIVE">Active</option><option value="INACTIVE">Inactive</option><option value="ARCHIVED">Archived</option></SelectField>
        {errors.root && <p role="alert" className="text-sm text-destructive">{errors.root.message}</p>}
        <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button type="submit" disabled={save.isPending}>Save variant</Button></div>
      </form>
    </Modal>
  )
}

export default function ProductDetailPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const admin = user?.role === 'ADMIN'
  const [variantDialog, setVariantDialog] = useState<{ variant: Variant | null } | null>(null)
  const [confirm, setConfirm] = useState<'archive' | 'delete' | { variant: Variant } | null>(null)
  const query = useQuery({ queryKey: queryKeys.products.detail(id), queryFn: () => productService.get(id) })
  const p = query.data
  const archive = useApiMutation(() => productService.archive(id), { invalidate: [queryKeys.products.all], success: 'Product archived', onSuccess: () => setConfirm(null) })
  const remove = useApiMutation(() => productService.remove(id), { invalidate: [queryKeys.products.all], success: 'Product deleted', onSuccess: () => navigate('/products') })
  const removeVariant = useApiMutation((vid: string) => productService.removeVariant(id, vid), { invalidate: [queryKeys.products.all], success: 'Variant deleted', onSuccess: () => setConfirm(null) })

  if (query.isLoading) return <PageContainer><LoadingState /></PageContainer>
  if (!p) return <PageContainer><ErrorState message={query.error?.message} onRetry={() => query.refetch()} /></PageContainer>
  return (
    <PageContainer>
      <PageHeader title={p.name} description={`${p.product_type} · ${money(p.sales_price)}`}
        actions={<><StatusBadge status={p.status} />{admin && <><Button variant="outline" size="sm" onClick={() => setConfirm('archive')} disabled={p.status === 'ARCHIVED'}>Archive</Button><Button variant="destructive" size="sm" onClick={() => setConfirm('delete')}>Delete</Button></>}</>} />
      <Card><CardContent className="pt-6"><ProductForm product={p} readOnly={!admin} /></CardContent></Card>
      <Section title="Variants" flush actions={admin ? <Button size="sm" onClick={() => setVariantDialog({ variant: null })}><Plus className="h-4 w-4" aria-hidden />Add variant</Button> : undefined}>
        <DataTable rows={p.variants} rowKey={(v) => v.id} emptyTitle="No variants" emptyDescription="Variants let one product be sold with different attribute prices, e.g. a brand surcharge."
          columns={[
            { header: 'Name', cell: (v) => v.name }, { header: 'Attribute', cell: (v) => `${v.attribute_name}: ${v.attribute_value}` },
            { header: 'Additional price', cell: (v) => money(v.additional_price) }, { header: 'Final price', cell: (v) => money((Number(p.sales_price) + Number(v.additional_price)).toFixed(2)) },
            { header: 'Status', cell: (v) => <StatusBadge status={v.status} /> },
            { header: '', cell: (v) => admin ? <div className="flex gap-2"><Button variant="outline" size="sm" onClick={() => setVariantDialog({ variant: v })}>Edit</Button><Button variant="ghost" size="sm" onClick={() => setConfirm({ variant: v })}>Delete</Button></div> : null },
          ]} />
      </Section>
      <VariantDialog product={p} variant={variantDialog?.variant ?? null} open={!!variantDialog} onClose={() => setVariantDialog(null)} />
      <ConfirmationDialog open={confirm === 'archive'} title="Archive this product?" description="Archived products can't be added to new quotations or subscriptions. Existing records keep working." confirmLabel="Archive" onConfirm={() => archive.mutate()} onCancel={() => setConfirm(null)} />
      <ConfirmationDialog open={confirm === 'delete'} destructive title="Delete this product?" description="Products used by plans, quotations, subscriptions or invoices can't be deleted; archive them instead." confirmLabel="Delete" onConfirm={() => remove.mutate()} onCancel={() => setConfirm(null)} />
      <ConfirmationDialog open={typeof confirm === 'object' && confirm !== null} destructive title="Delete this variant?" description="Variants used by quotations or subscriptions can't be deleted; set them to Archived instead." confirmLabel="Delete"
        onConfirm={() => typeof confirm === 'object' && confirm && removeVariant.mutate(confirm.variant.id)} onCancel={() => setConfirm(null)} />
    </PageContainer>
  )
}
