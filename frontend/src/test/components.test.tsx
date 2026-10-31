import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { DataTable } from '@/components/shared/DataTable'
import { EmptyState } from '@/components/shared/EmptyState'
import { ErrorState } from '@/components/shared/ErrorState'
import { Pagination } from '@/components/shared/Pagination'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { UserAvatar } from '@/components/shared/UserAvatar'

test('StatusBadge, UserAvatar and EmptyState render', () => {
  render(<><StatusBadge status="active" /><UserAvatar name="Ada Lovelace" /><EmptyState title="Nothing" description="Nope" /></>)
  expect(screen.getByText('active')).toBeInTheDocument()
  expect(screen.getByText('AL')).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Nothing' })).toBeInTheDocument()
})

test('DataTable renders rows, or the empty state with no rows', () => {
  const columns = [{ header: 'Name', cell: (r: { n: string }) => r.n }]
  const { rerender } = render(<DataTable columns={columns} rows={[{ n: 'Row one' }]} rowKey={(r) => r.n} />)
  expect(screen.getByText('Row one')).toBeInTheDocument()
  rerender(<DataTable columns={columns} rows={[]} rowKey={(r) => r.n} emptyTitle="No rows" />)
  expect(screen.getByText('No rows')).toBeInTheDocument()
})

test('Pagination disables Previous on the first page and calls back on Next', async () => {
  const onPageChange = vi.fn()
  render(<Pagination page={1} pageSize={10} total={25} onPageChange={onPageChange} />)
  expect(screen.getByRole('button', { name: /previous/i })).toBeDisabled()
  await userEvent.click(screen.getByRole('button', { name: /next/i }))
  expect(onPageChange).toHaveBeenCalledWith(2)
})

test('ErrorState offers retry', async () => {
  const retry = vi.fn()
  render(<ErrorState message="Boom" onRetry={retry} />)
  await userEvent.click(screen.getByRole('button', { name: /try again/i }))
  expect(retry).toHaveBeenCalled()
})
