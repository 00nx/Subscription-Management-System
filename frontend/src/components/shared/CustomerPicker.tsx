import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { queryKeys } from '@/lib/queryKeys'
import { customerService } from '@/services/sales.service'

/** Type to search customers (server-side, debounced), then pick one. Scales to thousands of customers. */
export function CustomerPicker({ value, onChange, error }: { value: string; onChange: (id: string) => void; error?: string }) {
  const [text, setText] = useState('')
  const [q, setQ] = useState('')
  useEffect(() => { const t = setTimeout(() => setQ(text), 250); return () => clearTimeout(t) }, [text])
  const { data } = useQuery({ queryKey: queryKeys.customers.list({ picker: q }), queryFn: () => customerService.list({ q, page_size: 20, is_active: 'true' }) })
  return (
    <div className="space-y-1.5">
      <Label htmlFor="customer-search">Customer</Label>
      <Input id="customer-search" type="search" placeholder="Search by name, email or CUS-…" value={text} onChange={(e) => setText(e.target.value)} />
      <select aria-label="Select customer" aria-invalid={!!error} value={value} onChange={(e) => onChange(e.target.value)} className="h-9 w-full rounded-md border border-border bg-card px-3 text-sm">
        <option value="">Select a customer…</option>
        {data?.items.map((c) => <option key={c.id} value={c.id}>{c.full_name} · {c.customer_number} · {c.email}</option>)}
      </select>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  )
}
