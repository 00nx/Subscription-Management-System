import type { HTMLAttributes, TdHTMLAttributes, ThHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

export const Table = ({ className, ...props }: HTMLAttributes<HTMLTableElement>) => (
  <div className="w-full overflow-x-auto">
    <table className={cn('w-full text-sm', className)} {...props} />
  </div>
)
export const TableHeader = (props: HTMLAttributes<HTMLTableSectionElement>) => <thead className="border-b border-border bg-muted/50" {...props} />
export const TableBody = (props: HTMLAttributes<HTMLTableSectionElement>) => <tbody className="divide-y divide-border" {...props} />
export const TableRow = (props: HTMLAttributes<HTMLTableRowElement>) => <tr {...props} />
export const TableHead = ({ className, ...props }: ThHTMLAttributes<HTMLTableCellElement>) => (
  <th className={cn('h-10 px-4 text-left font-medium text-muted-foreground', className)} {...props} />
)
export const TableCell = ({ className, ...props }: TdHTMLAttributes<HTMLTableCellElement>) => <td className={cn('px-4 py-3', className)} {...props} />
