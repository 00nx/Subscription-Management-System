import { Fragment, type ReactNode } from 'react'
import { DataTable } from '@/components/shared/DataTable'
import { Field, Section } from '@/components/shared/Section'
import { Card, CardContent } from '@/components/ui/card'
import { date, money } from '@/lib/format'
import type { Invoice } from '@/types'

/** The invoice document itself (customer, dates, lines, totals). Shared by the staff and customer detail pages. */
export function InvoiceView({ invoice: i, children }: { invoice: Invoice; children?: ReactNode }) {
  const c = i.customer_snapshot
  const m = (v: string) => money(v, i.currency)
  return (
    <>
      <Card><CardContent className="grid gap-5 pt-6 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Bill to">{c.name}{c.company_name ? <><br />{c.company_name}</> : null}<br />{c.email}{c.billing_address ? <><br />{c.billing_address}</> : null}</Field>
        <Field label="Issue date">{date(i.issue_date)}</Field><Field label="Due date">{date(i.due_date)} ({i.payment_terms_days} day terms)</Field>
        <Field label="Subscription">{i.subscription_number}</Field>
        {i.period_start && <Field label="Billing period">{date(i.period_start)} → {date(i.period_end)}</Field>}
        {c.tax_id && <Field label="Tax ID">{c.tax_id}</Field>}{i.notes && <Field label="Notes">{i.notes}</Field>}
      </CardContent></Card>
      <Section title="Lines" flush>
        <DataTable rows={i.lines} rowKey={(l) => l.id} columns={[
          { header: 'Description', cell: (l) => <>{l.description}{l.variants.map((v) => <span key={v.id} className="block text-xs text-muted-foreground">{v.attribute}: {v.value} (+{m(v.additional_price)})</span>)}</> }, { header: 'Qty', cell: (l) => l.quantity }, { header: 'Unit price', cell: (l) => m(l.unit_price) },
          { header: 'Discount', cell: (l) => m(l.discount_amount) }, { header: 'Tax', cell: (l) => `${l.tax_rate}% · ${m(l.tax_amount)}` }, { header: 'Total', cell: (l) => m(l.line_total) }]} />
        <dl className="ml-auto grid max-w-xs grid-cols-2 gap-x-6 gap-y-1 border-t border-border p-4 text-right text-sm">
          <dt>Subtotal</dt><dd>{m(i.subtotal)}</dd>
          {i.discount_breakdown.length ? i.discount_breakdown.map((d) => <Fragment key={d.name}><dt>Discount: {d.name}</dt><dd>-{m(d.amount)}</dd></Fragment>) : <><dt>Discount</dt><dd>-{m(i.discount_total)}</dd></>}
          {i.tax_breakdown.length ? i.tax_breakdown.map((t) => <Fragment key={`${t.name}${t.rate}`}><dt>{t.name} ({t.rate}%)</dt><dd>{m(t.amount)}</dd></Fragment>) : <><dt>Tax</dt><dd>{m(i.tax_total)}</dd></>}
          <dt className="font-semibold">Total</dt><dd className="font-semibold">{m(i.total)}</dd><dt>Paid</dt><dd>{m(i.amount_paid)}</dd><dt className="font-semibold">Outstanding</dt><dd className="font-semibold">{m(i.outstanding)}</dd>
        </dl>
      </Section>
      {children}
    </>
  )
}
