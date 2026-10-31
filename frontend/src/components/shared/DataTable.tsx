import type { ReactNode } from 'react'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { EmptyState } from './EmptyState'

export interface Column<T> {
  header: string
  cell: (row: T) => ReactNode
}

interface Props<T> {
  columns: Column<T>[]
  rows: T[]
  rowKey: (row: T) => string
  emptyTitle?: string
  emptyDescription?: string
}

export function DataTable<T>({ columns, rows, rowKey, emptyTitle = 'Nothing here yet', emptyDescription }: Props<T>) {
  if (rows.length === 0) return <EmptyState title={emptyTitle} description={emptyDescription} />
  return (
    <Table>
      <TableHeader>
        <TableRow>{columns.map((c) => <TableHead key={c.header}>{c.header}</TableHead>)}</TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={rowKey(row)}>{columns.map((c) => <TableCell key={c.header}>{c.cell(row)}</TableCell>)}</TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
