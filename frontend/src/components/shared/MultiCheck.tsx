interface Option { value: string; label: string }

/** Checkbox list for choosing several items (products, etc.). */
export function MultiCheck({ legend, options, value, onChange, empty = 'Nothing to choose from yet.' }: { legend: string; options: Option[]; value: string[]; onChange: (v: string[]) => void; empty?: string }) {
  return (
    <fieldset className="space-y-1.5">
      <legend className="text-sm font-medium">{legend}</legend>
      {options.length === 0 ? <p className="text-sm text-muted-foreground">{empty}</p> : (
        <div className="max-h-40 space-y-1 overflow-y-auto rounded-md border border-border p-2">
          {options.map((o) => (
            <label key={o.value} className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="h-4 w-4 accent-[var(--primary)]" checked={value.includes(o.value)}
                onChange={(e) => onChange(e.target.checked ? [...value, o.value] : value.filter((v) => v !== o.value))} />
              {o.label}
            </label>
          ))}
        </div>
      )}
    </fieldset>
  )
}
