import { useState } from 'react'
import { Link } from 'react-router-dom'
import { BellRing } from 'lucide-react'
import { PageContainer } from '@/components/layout/PageContainer'
import { ConfirmationDialog } from '@/components/shared/ConfirmationDialog'
import { FilterDropdown } from '@/components/shared/FilterDropdown'
import { PageHeader } from '@/components/shared/PageHeader'
import { QueryTable } from '@/components/shared/QueryTable'
import { SearchInput } from '@/components/shared/SearchInput'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Toolbar } from '@/components/shared/Toolbar'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useApiMutation } from '@/hooks/useApiMutation'
import { useListQuery } from '@/hooks/useListQuery'
import { useUrlState } from '@/hooks/useUrlState'
import { date, dateTime, label, money } from '@/lib/format'
import { queryKeys } from '@/lib/queryKeys'
import { overdueService } from '@/services/invoice.service'

/** Payable invoices past their due date: who owes what, since when, what they already paid, and a reminder action. */
export default function OverdueInvoicesPage() {
  const u = useUrlState()
  const [confirm, setConfirm] = useState<string[] | null>(null)
  const params = {
    q: u.value('q'), status: u.value('status'), due_from: u.value('due_from'), due_to: u.value('due_to'), min_amount: u.value('min_amount'), max_amount: u.value('max_amount'),
    min_days: u.value('min_days'), customer_id: u.value('customer_id'), page: u.page, sort: u.value('sort') || undefined,
  }
  const query = useListQuery((p) => [...queryKeys.invoices.list(p), 'overdue'], overdueService.list, params)
  const remind = useApiMutation((ids: string[]) => overdueService.remind(ids), {
    invalidate: [queryKeys.invoices.all], success: (r) => `${r.reminded} reminder(s) sent${r.skipped.length ? `, ${r.skipped.length} skipped (${r.skipped[0].reason})` : ''}`, onSuccess: () => setConfirm(null),
  })
  const shown = query.data?.items.map((i) => i.id) ?? []
  const input = (key: string, aria: string, extra?: object) => <Input className="w-32" aria-label={aria} placeholder={aria} value={u.value(key)} onChange={(e) => u.set(key, e.target.value)} {...extra} />
  return (
    <PageContainer>
      <PageHeader title="Overdue invoices" description="Confirmed invoices past their due date with a balance. A customer can be reminded once every 24 hours."
        actions={<Button variant="outline" disabled={!shown.length} onClick={() => setConfirm(shown)}><BellRing className="h-4 w-4" aria-hidden />Remind all shown</Button>} />
      <Toolbar>
        <SearchInput value={u.value('q')} onChange={(v) => u.set('q', v)} placeholder="Invoice, customer or email" />
        <FilterDropdown label="Status" value={u.value('status')} onChange={(v) => u.set('status', v)} options={[{ label: 'Confirmed (unpaid)', value: 'CONFIRMED' }, { label: 'Partially paid', value: 'PARTIALLY_PAID' }]} />
        {input('min_days', 'Min days overdue', { inputMode: 'numeric' })}
        {input('min_amount', 'Min amount', { inputMode: 'decimal' })}{input('max_amount', 'Max amount', { inputMode: 'decimal' })}
        <label className="flex items-center gap-1 text-sm">Due from <Input type="date" className="w-40" aria-label="Due from" value={u.value('due_from')} onChange={(e) => u.set('due_from', e.target.value)} /></label>
        <label className="flex items-center gap-1 text-sm">Due to <Input type="date" className="w-40" aria-label="Due to" value={u.value('due_to')} onChange={(e) => u.set('due_to', e.target.value)} /></label>
      </Toolbar>
      <QueryTable query={query} page={u.page} onPage={u.setPage} rowKey={(i) => i.id} emptyTitle="Nothing overdue" emptyDescription="Every issued invoice is either paid or not yet due."
        columns={[
          { header: 'Invoice', cell: (i) => <Link className="font-medium text-primary hover:underline" to={`/invoices/${i.id}`}>{i.number}</Link> },
          { header: 'Customer', cell: (i) => <>{i.customer_name}<span className="block text-xs text-muted-foreground">{i.customer_email}</span></> },
          { header: 'Status', cell: (i) => <StatusBadge status={i.status} /> }, { header: 'Due', cell: (i) => date(i.due_date) },
          { header: 'Days overdue', cell: (i) => <span className="font-medium text-destructive">{i.days_overdue}</span> },
          { header: 'Outstanding', cell: (i) => <>{money(i.outstanding, i.currency)}<span className="block text-xs text-muted-foreground">of {money(i.total, i.currency)}</span></> },
          { header: 'Payments', cell: (i) => i.payments.length ? i.payments.map((p) => <span key={p.id} className="block text-xs">{money(p.amount, i.currency)} · {label(p.method)}{p.payment_date ? ` · ${date(p.payment_date)}` : ''}</span>) : <span className="text-xs text-muted-foreground">None yet</span> },
          { header: 'Reminders', cell: (i) => i.reminder_count ? `${i.reminder_count} (last ${dateTime(i.last_reminded_at)})` : 'None' },
          { header: '', cell: (i) => <Button size="sm" variant="outline" onClick={() => setConfirm([i.id])}>Remind</Button> },
        ]} />
      <ConfirmationDialog open={!!confirm} title={`Send ${confirm?.length ?? 0} payment reminder(s)?`} confirmLabel="Send reminders"
        description="Each customer gets an email and an in-app notification. Invoices reminded in the last 24 hours are skipped." onConfirm={() => confirm && remind.mutate(confirm)} onCancel={() => setConfirm(null)} />
    </PageContainer>
  )
}
