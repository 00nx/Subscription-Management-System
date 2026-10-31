import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, BarChart3, Banknote, FileText, Receipt, Repeat, TrendingUp, Users, Wallet } from 'lucide-react'
import { CustomerPicker } from '@/components/shared/CustomerPicker'
import { PageContainer } from '@/components/layout/PageContainer'
import { ErrorState } from '@/components/shared/ErrorState'
import { LoadingState } from '@/components/shared/LoadingState'
import { PageHeader } from '@/components/shared/PageHeader'
import { Section } from '@/components/shared/Section'
import { StatCard } from '@/components/shared/StatCard'
import { Input } from '@/components/ui/input'
import { useAuth } from '@/hooks/useAuth'
import { useUrlState } from '@/hooks/useUrlState'
import { dateTime, FREQUENCY_LABEL, label, money } from '@/lib/format'
import { queryKeys } from '@/lib/queryKeys'
import { planService } from '@/services/catalog.service'
import { analyticsService } from '@/services/user.service'
import { AmountArea, AmountLine, ChartCard, Donut, GrowthChart, OutstandingBars } from './charts'

const RANGES = [['today', 'Today'], ['last_7_days', 'Last 7 days'], ['last_30_days', 'Last 30 days'], ['this_month', 'This month'], ['last_month', 'Last month'], ['this_year', 'This year'], ['custom', 'Custom range']]

export default function DashboardPage() {
  const { user } = useAuth()
  const u = useUrlState({ range: 'last_30_days' })
  const range = u.value('range')
  const custom = range === 'custom'
  const params = {
    range, date_from: custom ? u.value('from') : undefined, date_to: custom ? u.value('to') : undefined, billing_frequency: u.value('frequency') || undefined,
    subscription_status: u.value('sub_status') || undefined, invoice_status: u.value('inv_status') || undefined, plan_id: u.value('plan_id') || undefined, customer_id: u.value('customer_id') || undefined,
  }
  const plans = useQuery({ queryKey: queryKeys.plans.list({ dashboard: true }), queryFn: () => planService.list({ page_size: 100 }) })
  const filtered = ['frequency', 'sub_status', 'inv_status', 'plan_id', 'customer_id'].some((k) => u.value(k))
  const sel = 'h-9 rounded-md border border-border bg-card px-3 text-sm'
  const ready = !custom || (!!u.value('from') && !!u.value('to'))
  const query = useQuery({ queryKey: queryKeys.analytics.dashboard(params), queryFn: () => analyticsService.dashboard(params), enabled: ready, refetchInterval: 60_000 })
  const d = query.data
  const full = user?.role === 'ADMIN'

  return (
    <PageContainer>
      <PageHeader title="Dashboard" description={full ? 'Revenue, subscriptions and collections.' : 'Operational overview.'} actions={
        <div className="flex flex-wrap items-center gap-2">
          <select aria-label="Date range" className="h-9 rounded-md border border-border bg-card px-3 text-sm" value={range} onChange={(e) => u.set('range', e.target.value)}>
            {RANGES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          {custom && <><Input type="date" aria-label="From date" className="w-40" value={u.value('from')} onChange={(e) => u.set('from', e.target.value)} /><Input type="date" aria-label="To date" className="w-40" value={u.value('to')} onChange={(e) => u.set('to', e.target.value)} /></>}
        </div>} />
      <div className="flex flex-wrap items-end gap-2" role="group" aria-label="Dashboard filters">
        <select aria-label="Billing frequency" className={sel} value={u.value('frequency')} onChange={(e) => u.set('frequency', e.target.value)}><option value="">All frequencies</option>{Object.entries(FREQUENCY_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
        <select aria-label="Subscription status" className={sel} value={u.value('sub_status')} onChange={(e) => u.set('sub_status', e.target.value)}><option value="">Any subscription status</option>{['ACTIVE', 'PAUSED', 'CONFIRMED', 'EXPIRED', 'CLOSED'].map((s) => <option key={s} value={s}>{label(s)}</option>)}</select>
        <select aria-label="Invoice status" className={sel} value={u.value('inv_status')} onChange={(e) => u.set('inv_status', e.target.value)}><option value="">Any invoice status</option>{['CONFIRMED', 'PARTIALLY_PAID', 'PAID', 'CANCELLED'].map((s) => <option key={s} value={s}>{label(s)}</option>)}</select>
        <select aria-label="Plan" className={sel} value={u.value('plan_id')} onChange={(e) => u.set('plan_id', e.target.value)}><option value="">All plans</option>{plans.data?.items.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select>
        <div className="w-72"><CustomerPicker value={u.value('customer_id')} onChange={(v) => u.set('customer_id', v)} /></div>
        {filtered && <button type="button" className="h-9 text-sm text-primary hover:underline" onClick={() => u.setMany({ frequency: '', sub_status: '', inv_status: '', plan_id: '', customer_id: '' })}>Clear filters</button>}
      </div>
      {!ready ? <p className="text-sm text-muted-foreground">Choose a start and end date.</p> : query.isLoading ? <LoadingState /> : query.error || !d ? <ErrorState message={query.error?.message} onRetry={() => query.refetch()} /> : (
        <>
          <p className="text-xs text-muted-foreground">Period: {d.range.date_from} to {d.range.date_to}. Collected revenue counts successful payments only.</p>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Active subscriptions" value={d.kpis.active_subscriptions} icon={<Repeat className="h-5 w-5" />} />
            {d.kpis.mrr != null && <StatCard label="MRR" value={money(d.kpis.mrr)} hint="Monthly recurring revenue" icon={<TrendingUp className="h-5 w-5" />} />}
            {d.kpis.arr != null && <StatCard label="ARR" value={money(d.kpis.arr)} hint="MRR × 12" icon={<BarChart3 className="h-5 w-5" />} />}
            {d.kpis.revenue_collected != null && <StatCard label="Revenue collected" value={money(d.kpis.revenue_collected)} hint="In the selected period" icon={<Banknote className="h-5 w-5" />} />}
            <StatCard label="Outstanding" value={money(d.kpis.outstanding_amount)} hint="Unpaid invoice balances" icon={<Wallet className="h-5 w-5" />} />
            <StatCard label="Overdue invoices" value={d.kpis.overdue_invoices} icon={<AlertTriangle className="h-5 w-5" />} />
            <StatCard label="Total customers" value={d.kpis.total_customers} icon={<Users className="h-5 w-5" />} />
            <StatCard label="Total invoices" value={d.kpis.total_invoices} hint={d.kpis.revenue_billed != null ? `${money(d.kpis.revenue_billed)} billed in the period` : 'Issued in the period'} icon={<Receipt className="h-5 w-5" />} />
            {d.kpis.total_payments != null && <StatCard label="Total payments" value={money(d.kpis.total_payments)} hint={`${d.kpis.payments_count} successful payment(s) in the period`} icon={<FileText className="h-5 w-5" />} />}
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            {d.revenue_over_time && <ChartCard title="Revenue over time" empty={d.revenue_over_time.every((p) => Number(p.amount) === 0)}><AmountArea data={d.revenue_over_time} /></ChartCard>}
            {d.mrr_trend && <ChartCard title="MRR trend (12 months)" empty={d.mrr_trend.every((p) => Number(p.amount) === 0)}><AmountLine data={d.mrr_trend} name="MRR" /></ChartCard>}
            <ChartCard title="Subscription growth" empty={d.subscription_growth.every((p) => p.total === 0)}><GrowthChart data={d.subscription_growth} /></ChartCard>
            <ChartCard title="Active subscriptions by plan" empty={d.active_by_plan.length === 0}>
              <Donut data={d.active_by_plan.map((x) => ({ name: x.plan, value: x.count }))} /></ChartCard>
            <ChartCard title="Subscription status" empty={d.subscription_status.every((s) => s.count === 0)}><Donut data={d.subscription_status.filter((s) => s.count > 0).map((s) => ({ name: label(s.status), value: s.count }))} /></ChartCard>
            <ChartCard title="Payment status" empty={d.payment_status.every((s) => s.count === 0)}>
              <Donut data={d.payment_status.filter((s) => s.count > 0).map((s) => ({ name: label(s.status), value: s.count, extra: s.amount }))} tooltip={(x) => `${x.value} payment(s) · ${money(x.extra)}`} /></ChartCard>
            {d.revenue_over_time && <ChartCard title="Outstanding vs collected" empty={Number(d.outstanding_vs_collected.outstanding) === 0 && Number(d.outstanding_vs_collected.collected ?? 0) === 0}><OutstandingBars {...d.outstanding_vs_collected} /></ChartCard>}
          </div>
          <Section title="Recent activity" flush>
            {d.recent_activity.length === 0 ? <p className="p-6 text-sm text-muted-foreground">Nothing has happened yet.</p> : (
              <ul className="divide-y divide-border">{d.recent_activity.map((a, i) => (
                <li key={i} className="flex items-start justify-between gap-4 px-5 py-3 text-sm"><span><span className="font-medium">{a.title}</span>{a.detail && <span className="block text-muted-foreground">{a.detail}</span>}</span><time className="shrink-0 text-xs text-muted-foreground" dateTime={a.at}>{dateTime(a.at)}</time></li>))}</ul>)}
          </Section>
        </>
      )}
    </PageContainer>
  )
}
