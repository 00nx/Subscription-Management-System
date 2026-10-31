import { Search } from 'lucide-react'
import { Input } from '@/components/ui/input'

export function SearchInput({ value, onChange, placeholder = 'Search…' }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <div className="relative max-w-xs flex-1">
      <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" aria-hidden />
      <Input type="search" aria-label={placeholder} className="pl-9" value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
    </div>
  )
}
