import { Search } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Input } from '@/components/ui/input'

// Reference prefixes jump straight to the right list; anything else searches customers.
const TARGETS: [RegExp, string][] = [[/^inv-/i, '/invoices'], [/^sub-/i, '/subscriptions'], [/^quo-/i, '/quotations'], [/^cus-/i, '/customers']]

export function HeaderSearch() {
  const [text, setText] = useState('')
  const navigate = useNavigate()
  const submit = (e: FormEvent) => {
    e.preventDefault()
    const q = text.trim()
    if (!q) return
    const to = TARGETS.find(([re]) => re.test(q))?.[1] ?? '/customers'
    navigate(`${to}?q=${encodeURIComponent(q)}`)
    setText('')
  }
  return (
    <form role="search" onSubmit={submit} className="relative hidden max-w-xs flex-1 sm:block">
      <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" aria-hidden />
      <Input aria-label="Search customers, invoices, subscriptions" placeholder="Search customers, INV-…, SUB-…" className="pl-9" value={text} onChange={(e) => setText(e.target.value)} />
    </form>
  )
}
