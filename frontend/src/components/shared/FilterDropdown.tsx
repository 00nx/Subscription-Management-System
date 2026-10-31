export interface FilterOption { label: string; value: string }

// Native <select>: accessible and mobile-friendly with no extra dependency.
export function FilterDropdown({ label, value, options, onChange }: { label: string; value: string; options: FilterOption[]; onChange: (v: string) => void }) {
  return (
    <select aria-label={label} value={value} onChange={(e) => onChange(e.target.value)} className="h-9 rounded-md border border-border bg-card px-3 text-sm">
      <option value="">{label}: All</option>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  )
}
