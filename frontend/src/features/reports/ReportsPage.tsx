import { ArrowDown, ArrowUp, Download, FileText } from 'lucide-react'
import type { ReactNode } from 'react'
import { PageContainer } from '@/components/layout/PageContainer'
import { EmptyState } from '@/components/shared/EmptyState'
import { ErrorState } from '@/components/shared/ErrorState'
import { FilterDropdown } from '@/components/shared/FilterDropdown'
import { LoadingState } from '@/components/shared/LoadingState'
import { PageHeader } from '@/components/shared/PageHeader'
import { Pagination } from '@/components/shared/Pagination'
import { SearchInput } from '@/components/shared/SearchInput'
import { StatCard } from '@/components/shared/StatCard'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Toolbar } from '@/components/shared/Toolbar'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useAuth } from '@/hooks/useAuth'
import { useApiMutation } from '@/hooks/useApiMutation'
import { useListQuery } from '@/hooks/useListQuery'
import { useUrlState } from '@/hooks/useUrlState'
import { cn } from '@/lib/utils'
import { date, dateTime, FREQUENCY_LABEL, label, money } from '@/lib/format'
import { queryKeys } from '@/lib/queryKeys'
import { reportService } from '@/services/user.service'
import type { ReportResult } from '@/types'

/* eslint-disable @typescript-eslint/no-explicit-any */
interface Col { key: string; header: string; sort?: string; cell?: (v: any, row: any) => ReactNode }
const m = (v: any) => money(v)
const badge = (v: any) => <StatusBadge status={String(v)} />

const RECEIVABLE_COLS: Col[] = [{ key: 'number', header: 'Invoice', sort: 'number' }, { key: 'customer', header: 'Customer' }, { key: 'status', header: 'Status', cell: badge }, { key: 'issue_date', header: 'Issued', cell: date },
  { key: 'due_date', header: 'Due', sort: 'due_date', cell: date }, { key: 'days_overdue', header: 'Days overdue' }, { key: 'total', header: 'Total', sort: 'total', cell: m }, { key: 'amount_paid', header: 'Paid', cell: m }, { key: 'outstanding', header: 'Outstanding', sort: 'outstanding', cell: m }]
const AGING = (s: any) => <>{[['1-30 days', s.overdue_1_30_days], ['31-60 days', s.overdue_31_60_days], ['61-90 days', s.overdue_61_90_days], ['Over 90 days', s.overdue_over_90_days]].map(([l, v]: any) => <StatCard key={l} label={`Overdue ${l}`} value={v.count} hint={money(v.amount)} />)}</>

const TABS: Record<string, { title: string; admin?: boolean; searchable?: boolean; filters?: { param: string; label: string; options: string[] }[]; cols: Col[]; cards: (s: any) => ReactNode }> = {
  subscriptions: {
    title: 'Subscriptions', searchable: true, filters: [{ param: 'status', label: 'Status', options: ['ACTIVE', 'PAUSED', 'CLOSED', 'EXPIRED', 'CONFIRMED', 'DRAFT'] }, { param: 'billing_frequency', label: 'Frequency', options: Object.keys(FREQUENCY_LABEL) }],
    cols: [{ key: 'number', header: 'Number', sort: 'number' }, { key: 'customer', header: 'Customer', sort: 'customer' }, { key: 'plan', header: 'Plan', sort: 'plan' }, { key: 'status', header: 'Status', sort: 'status', cell: badge },
      { key: 'billing_frequency', header: 'Frequency', cell: (v) => FREQUENCY_LABEL[v] }, { key: 'start_date', header: 'Start', sort: 'start_date', cell: date }, { key: 'expiry_date', header: 'Expiry', cell: date }, { key: 'total', header: 'Total / period', sort: 'total', cell: m }],
    cards: (s) => <>{[['Total', s.total], ['Active', s.active], ['Cancelled', s.cancelled], ['Expired', s.expired], ['Paused', s.paused]].map(([l, v]) => <StatCard key={l as string} label={l as string} value={v as number} />)}</>,
  },
  invoices: {
    title: 'Invoices', searchable: true, filters: [{ param: 'status', label: 'Status', options: ['DRAFT', 'CONFIRMED', 'PARTIALLY_PAID', 'PAID', 'CANCELLED'] }, { param: 'overdue', label: 'Overdue', options: ['true', 'false'] }],
    cols: [{ key: 'number', header: 'Number', sort: 'number' }, { key: 'customer', header: 'Customer' }, { key: 'status', header: 'Status', sort: 'status', cell: (v, r) => badge(r.overdue ? 'OVERDUE' : v) }, { key: 'issue_date', header: 'Issued', sort: 'issue_date', cell: date },
      { key: 'due_date', header: 'Due', sort: 'due_date', cell: date }, { key: 'total', header: 'Total', sort: 'total', cell: m }, { key: 'amount_paid', header: 'Paid', cell: m }, { key: 'outstanding', header: 'Outstanding', sort: 'outstanding', cell: m }],
    cards: (s) => <><StatCard label="Total invoices" value={s.total_invoices} /><StatCard label="Paid" value={s.paid.count} /><StatCard label="Partially paid" value={s.partially_paid.count} hint={`${money(s.partially_paid.amount)} left`} />
      <StatCard label="Outstanding" value={s.outstanding.count} hint={money(s.outstanding.amount)} /><StatCard label="Overdue" value={s.overdue.count} hint={money(s.overdue.amount)} /></>,
  },
  payments: {
    title: 'Payments', searchable: true, filters: [{ param: 'status', label: 'Status', options: ['SUCCESS', 'PENDING', 'FAILED', 'CANCELLED'] }, { param: 'method', label: 'Method', options: ['CASH', 'BANK_TRANSFER', 'CARD', 'UPI', 'OTHER'] }],
    cols: [{ key: 'invoice', header: 'Invoice', sort: 'invoice' }, { key: 'method', header: 'Method', sort: 'method', cell: label }, { key: 'amount', header: 'Amount', sort: 'amount', cell: m }, { key: 'status', header: 'Status', sort: 'status', cell: badge },
      { key: 'reference', header: 'Reference' }, { key: 'payment_date', header: 'Paid on', sort: 'payment_date', cell: dateTime }],
    cards: (s) => <><StatCard label="Successful" value={s.successful.count} hint={money(s.successful.amount)} /><StatCard label="Failed" value={s.failed.count} hint={money(s.failed.amount)} /><StatCard label="Pending" value={s.pending.count} hint={money(s.pending.amount)} />
      {s.by_method.map((x: any) => <StatCard key={x.method} label={label(x.method)} value={money(x.amount)} hint={`${x.count} payment(s)`} />)}</>,
  },
  outstanding: {
    title: 'Outstanding', searchable: true, cols: RECEIVABLE_COLS,
    cards: (s) => <><StatCard label="Outstanding" value={money(s.outstanding_amount)} hint={`${s.count} invoice(s)`} /><StatCard label="Not yet due" value={s.not_yet_due.count} hint={money(s.not_yet_due.amount)} />{AGING(s)}</>,
  },
  overdue: {
    title: 'Overdue', searchable: true, cols: RECEIVABLE_COLS,
    cards: (s) => <><StatCard label="Overdue" value={money(s.outstanding_amount)} hint={`${s.count} invoice(s)`} />{AGING(s)}</>,
  },
  renewals: {
    title: 'Renewals', searchable: true, filters: [{ param: 'auto_renew', label: 'Auto-renew', options: ['true', 'false'] }],
    cols: [{ key: 'number', header: 'Subscription', sort: 'number' }, { key: 'customer', header: 'Customer', sort: 'customer' }, { key: 'plan', header: 'Plan' }, { key: 'expiry_date', header: 'Expires', sort: 'expiry_date', cell: date },
      { key: 'days_to_expiry', header: 'Days left' }, { key: 'auto_renew', header: 'Auto-renew', cell: (v) => (v ? 'Yes' : 'No') }, { key: 'renewal_count', header: 'Renewals' }, { key: 'total', header: 'Per period', sort: 'total', cell: m }],
    cards: (s) => <><StatCard label="Expiring (next 30 days)" value={s.expiring} hint={`${money(s.value_per_period)} per period`} /><StatCard label="Auto-renewing" value={s.auto_renewing} /><StatCard label="Need manual renewal" value={s.manual_renewal_needed} />
      <StatCard label="Renewed (period)" value={s.renewed_in_range} /><StatCard label="Expired (period)" value={s.expired_in_range} /></>,
  },
  revenue: {
    title: 'Revenue', admin: true,
    cols: [], cards: (s) => <><StatCard label="MRR" value={money(s.mrr)} /><StatCard label="ARR" value={money(s.arr)} /><StatCard label="Collected (period)" value={money(s.revenue_collected)} /></>,
  },
}

function revenueCols(group: string): Col[] {
  if (group === 'period') return [{ key: 'label', header: 'Month', sort: 'label' }, { key: 'invoiced', header: 'Invoiced', cell: m }, { key: 'collected', header: 'Collected', cell: m }]
  return [{ key: 'label', header: group === 'product' ? 'Product' : 'Plan', sort: 'label' }, { key: 'invoiced', header: 'Invoiced', sort: 'invoiced', cell: m }, group === 'product' ? { key: 'quantity', header: 'Units' } : { key: 'invoices', header: 'Invoices' }]
}

export default function ReportsPage() {
  const { user } = useAuth()
  const admin = user?.role === 'ADMIN'
  const u = useUrlState({ tab: 'subscriptions' })
  const tabKey = !admin && TABS[u.value('tab')]?.admin ? 'subscriptions' : u.value('tab') in TABS ? u.value('tab') : 'subscriptions'
  const tab = TABS[tabKey]
  const group = u.value('group') || 'period'
  const filterParams = Object.fromEntries((tab.filters ?? []).map((f) => [f.param, u.value(f.param)]))
  const params = { ...filterParams, q: u.value('q'), date_from: u.value('from'), date_to: u.value('to'), sort: u.value('sort'), page: u.page, page_size: 15,
    ...(tabKey === 'revenue' ? { group_by: group, range: u.value('from') && u.value('to') ? 'custom' : 'this_year' } : {}) }
  const query = useListQuery<any>((p) => queryKeys.reports.get(tabKey, p), async (p) => {
    const r: ReportResult = await reportService.get(tabKey, p)
    return { ...r.rows, items: r.rows.items, summary: r.summary, tab: tabKey } as any  // tagged so a kept-previous result is never rendered by another tab
  }, params)
  const exportCsv = useApiMutation(() => reportService.csv(tabKey, { ...params, page: undefined, page_size: undefined }), { success: 'CSV exported' })
  const exportPdf = useApiMutation(() => reportService.pdf(tabKey, { ...params, page: undefined, page_size: undefined }), { success: 'PDF exported' })

  const cols = tabKey === 'revenue' ? revenueCols(group) : tab.cols
  const data: any = query.data
  const sort = u.value('sort')
  const toggleSort = (key: string) => u.set('sort', sort === key ? `-${key}` : key)

  return (
    <PageContainer>
      <PageHeader title="Reports" description="Generated from live database records. Export any report to CSV or PDF." actions={<>
        <Button variant="outline" onClick={() => exportCsv.mutate()} disabled={exportCsv.isPending}><Download className="h-4 w-4" aria-hidden />Export CSV</Button>
        <Button variant="outline" onClick={() => exportPdf.mutate()} disabled={exportPdf.isPending}><FileText className="h-4 w-4" aria-hidden />Export PDF</Button></>} />
      <div role="tablist" aria-label="Report type" className="flex flex-wrap gap-1 border-b border-border">
        {Object.entries(TABS).filter(([, t]) => admin || !t.admin).map(([k, t]) => (
          <button key={k} role="tab" aria-selected={k === tabKey} onClick={() => u.setMany({ tab: k, ...Object.fromEntries(['q', 'sort', 'from', 'to', 'group', ...Object.keys(filterParams)].map((x) => [x, ''])) })}
            className={cn('-mb-px border-b-2 px-4 py-2 text-sm font-medium', k === tabKey ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground')}>{t.title}</button>))}
      </div>
      <Toolbar>
        {tab.searchable && <SearchInput value={u.value('q')} onChange={(v) => u.set('q', v)} placeholder="Search…" />}
        {tabKey === 'revenue' && <FilterDropdown label="Group by" value={group === 'period' ? '' : group} onChange={(v) => u.set('group', v)} options={[{ label: 'Product', value: 'product' }, { label: 'Plan', value: 'plan' }]} />}
        {(tab.filters ?? []).map((f) => <FilterDropdown key={f.param} label={f.label} value={u.value(f.param)} onChange={(v) => u.set(f.param, v)} options={f.options.map((o) => ({ label: label(o), value: o }))} />)}
        <label className="flex items-center gap-1 text-sm">From <Input type="date" className="w-40" aria-label="From date" value={u.value('from')} onChange={(e) => u.set('from', e.target.value)} /></label>
        <label className="flex items-center gap-1 text-sm">To <Input type="date" className="w-40" aria-label="To date" value={u.value('to')} onChange={(e) => u.set('to', e.target.value)} /></label>
      </Toolbar>
      {query.isLoading || (data && data.tab !== tabKey) ? <LoadingState /> : query.error || !data ? <ErrorState message={query.error?.message} onRetry={() => query.refetch()} /> : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">{tab.cards(data.summary)}</div>
          {tabKey === 'subscriptions' && (
            <div className="grid gap-3 md:grid-cols-2">
              <Card className="p-4 text-sm"><p className="mb-2 font-medium">By plan</p>{data.summary.by_plan.length === 0 ? <p className="text-muted-foreground">No data.</p> : <ul className="space-y-1">{data.summary.by_plan.map((x: any) => <li key={x.plan} className="flex justify-between"><span>{x.plan}</span><span>{x.count}</span></li>)}</ul>}</Card>
              <Card className="p-4 text-sm"><p className="mb-2 font-medium">By billing frequency</p>{data.summary.by_frequency.length === 0 ? <p className="text-muted-foreground">No data.</p> : <ul className="space-y-1">{data.summary.by_frequency.map((x: any) => <li key={x.frequency} className="flex justify-between"><span>{FREQUENCY_LABEL[x.frequency]}</span><span>{x.count}</span></li>)}</ul>}</Card>
            </div>)}
          <Card>
            {data.items.length === 0 ? <EmptyState title="No rows for these filters" description="Adjust the filters or date range." /> : (
              <>
                <Table>
                  <TableHeader><TableRow>{cols.map((c) => (
                    <TableHead key={c.key} aria-sort={c.sort && (sort === c.sort ? 'ascending' : sort === `-${c.sort}` ? 'descending' : 'none') || undefined}>
                      {c.sort ? <button type="button" className="inline-flex items-center gap-1 hover:text-foreground" onClick={() => toggleSort(c.sort!)}>{c.header}{sort === c.sort ? <ArrowUp className="h-3 w-3" aria-hidden /> : sort === `-${c.sort}` ? <ArrowDown className="h-3 w-3" aria-hidden /> : null}</button> : c.header}
                    </TableHead>))}</TableRow></TableHeader>
                  <TableBody>{data.items.map((row: any, i: number) => <TableRow key={i}>{cols.map((c) => <TableCell key={c.key}>{c.cell ? c.cell(row[c.key], row) : (row[c.key] ?? '-')}</TableCell>)}</TableRow>)}</TableBody>
                </Table>
                <Pagination page={u.page} pageSize={data.page_size} total={data.total} onPageChange={u.setPage} />
              </>)}
          </Card>
        </>)}
    </PageContainer>
  )
}
