import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'

export function Pagination({ page, pageSize, total, onPageChange }: { page: number; pageSize: number; total: number; onPageChange: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between border-t border-border px-4 py-3 text-sm text-muted-foreground">
      <span>Page {page} of {pages} · {total} total</span>
      <div className="flex gap-2">
        <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)}><ChevronLeft className="h-4 w-4" aria-hidden />Previous</Button>
        <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => onPageChange(page + 1)}>Next<ChevronRight className="h-4 w-4" aria-hidden /></Button>
      </div>
    </nav>
  )
}
