import { Controller, useFieldArray, useWatch } from 'react-hook-form'
import { Plus, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { VariantChecks } from './VariantChecks'
import type { Product } from '@/types'

/* eslint-disable @typescript-eslint/no-explicit-any */
// Generic over the host form's shape, so control/register are deliberately loose.
interface Props { control: any; register: any; products: Product[]; name?: string }

export interface LineValues { product_id: string; variant_ids: string[]; quantity: string; unit_price: string }
export const emptyLine: LineValues = { product_id: '', variant_ids: [], quantity: '1', unit_price: '' }

const sel = 'h-9 w-full rounded-md border border-border bg-card px-2 text-sm'
const inp = 'h-9 w-full rounded-md border border-border bg-card px-2 text-sm'

/** Editable lines: product, optional variant, quantity, optional negotiated unit price (blank = plan/product price). */
export function LinesEditor({ control, register, products, name = 'lines' }: Props) {
  const { fields, append, remove } = useFieldArray({ control, name })
  // `fields` only holds the values from when each row was added; the live selection comes from useWatch.
  const live = (useWatch({ control, name }) ?? []) as LineValues[]
  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium">Lines</legend>
      {fields.length === 0 && <p className="text-sm text-muted-foreground">No lines: the template or plan default will be used.</p>}
      {fields.map((f, i) => {
        const product = products.find((p) => p.id === live[i]?.product_id)
        return (
          <div key={f.id} className="grid grid-cols-12 items-end gap-2">
            <label className="col-span-12 text-xs sm:col-span-4">Product
              <select className={sel} {...register(`${name}.${i}.product_id`)}><option value="">Select…</option>{products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
            <div className="col-span-6 text-xs sm:col-span-3"><span id={`${name}-${i}-variants`}>Variants</span>
              <Controller control={control} name={`${name}.${i}.variant_ids`} render={({ field }) => <VariantChecks variants={product?.variants ?? []} value={field.value ?? []} onChange={field.onChange} />} /></div>
            <label className="col-span-3 text-xs sm:col-span-1">Qty<input className={inp} inputMode="numeric" {...register(`${name}.${i}.quantity`)} /></label>
            <label className="col-span-3 text-xs sm:col-span-3">Unit price<input className={inp} inputMode="decimal" placeholder="default" {...register(`${name}.${i}.unit_price`)} /></label>
            <Button type="button" variant="ghost" size="icon" aria-label="Remove line" className="col-span-12 sm:col-span-1" onClick={() => remove(i)}><Trash2 className="h-4 w-4" /></Button>
          </div>
        )
      })}
      <Button type="button" variant="outline" size="sm" onClick={() => append(emptyLine)}><Plus className="h-4 w-4" aria-hidden />Add line</Button>
    </fieldset>
  )
}

/** Converts editor values to API line inputs, dropping empty rows. */
export const toLineInputs = (lines: LineValues[]) =>
  lines.filter((l) => l.product_id).map((l) => ({ product_id: l.product_id, variant_ids: l.variant_ids, quantity: Number(l.quantity) || 1, unit_price: l.unit_price || null }))
