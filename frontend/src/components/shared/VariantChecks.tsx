import { money } from '@/lib/format'
interface Option { id: string; name: string; additional_price: string; status?: string }

/** Pick any number of variants; the final price is base + every selected adjustment. */
export function VariantChecks({ variants, value, onChange }: { variants: Option[]; value: string[]; onChange: (v: string[]) => void }) {
  const active = variants.filter((v) => !v.status || v.status === 'ACTIVE')
  if (!active.length) return <p className="text-xs text-muted-foreground">No variants</p>
  const toggle = (id: string) => onChange(value.includes(id) ? value.filter((x) => x !== id) : [...value, id])
  return (
    <div role="group" aria-label="Variants" className="flex flex-wrap gap-x-3 gap-y-1">
      {active.map((v) => (
        <label key={v.id} className="flex items-center gap-1 text-xs">
          <input type="checkbox" checked={value.includes(v.id)} onChange={() => toggle(v.id)} />{v.name} (+{money(v.additional_price)})
        </label>
      ))}
    </div>
  )
}
