import { useQuery } from '@tanstack/react-query'
import { PageContainer } from '@/components/layout/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { QueryTable } from '@/components/shared/QueryTable'
import { Section } from '@/components/shared/Section'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Button } from '@/components/ui/button'
import { useApiMutation } from '@/hooks/useApiMutation'
import { useListQuery } from '@/hooks/useListQuery'
import { useUrlState } from '@/hooks/useUrlState'
import { dateTime } from '@/lib/format'
import { queryKeys } from '@/lib/queryKeys'
import { auditService, emailService } from '@/services/user.service'

export default function SettingsPage() {
  const u = useUrlState()
  const emails = useListQuery((p) => [...queryKeys.audit.list(p), 'emails'], emailService.list, { page: u.page, status: u.value('email_status') || undefined, page_size: 10 })
  const summary = useQuery({ queryKey: [...queryKeys.audit.all, 'email-summary'], queryFn: emailService.summary })
  const retry = useApiMutation((id: string) => emailService.retry(id), { invalidate: [queryKeys.audit.all], success: (e) => `Email ${e.status.toLowerCase()}` })
  const audit = useListQuery(queryKeys.audit.list, auditService.list, { page: u.page, entity_type: u.value('entity') })
  return (
    <PageContainer>
      <PageHeader title="Settings" description="Email delivery and the audit trail." />
      <Section title="Email delivery" flush actions={
        <select aria-label="Email status" className="h-8 rounded-md border border-border bg-card px-2 text-sm" value={u.value('email_status')} onChange={(e) => u.set('email_status', e.target.value)}>
          <option value="">All statuses</option>{['SENT', 'FAILED', 'QUEUED', 'SUPPRESSED'].map((s) => <option key={s} value={s}>{s.charAt(0) + s.slice(1).toLowerCase()}</option>)}
        </select>}>
        <p className="px-5 pt-3 text-sm text-muted-foreground">{summary.data ? `${summary.data.sent} sent · ${summary.data.failed} failed · ${summary.data.queued} queued${summary.data.suppressed ? ` · ${summary.data.suppressed} suppressed (not sent by configuration)` : ''}` : ''}</p>
        <QueryTable bare query={emails} page={u.page} onPage={u.setPage} rowKey={(e) => e.id} emptyTitle="No emails yet" emptyDescription="Registration, invoices, payments and reminders are listed here with their delivery result." columns={[
          { header: 'When', cell: (e) => dateTime(e.created_at) }, { header: 'To', cell: (e) => e.to_email }, { header: 'Subject', cell: (e) => e.subject },
          { header: 'Status', cell: (e) => <StatusBadge status={e.status === 'SENT' ? 'SUCCESS' : e.status === 'FAILED' ? 'FAILED' : 'PENDING'} /> },
          { header: 'Attempts', cell: (e) => e.attempts }, { header: 'Error', cell: (e) => e.error ?? '' },
          { header: '', cell: (e) => e.status === 'FAILED' ? <Button size="sm" variant="outline" onClick={() => retry.mutate(e.id)} disabled={retry.isPending}>Retry</Button> : null }]} />
      </Section>
      <Section title="Audit log" flush actions={
        <select aria-label="Entity" className="h-8 rounded-md border border-border bg-card px-2 text-sm" value={u.value('entity')} onChange={(e) => u.set('entity', e.target.value)}>
          <option value="">All entities</option>
          {['product', 'plan', 'subscription', 'invoice', 'payment', 'discount', 'user', 'tax', 'quotation'].map((e) => <option key={e} value={e}>{e}</option>)}
        </select>}>
        <QueryTable bare query={audit} page={u.page} onPage={u.setPage} rowKey={(a) => a.id} emptyTitle="No audit entries" columns={[
          { header: 'When', cell: (a) => dateTime(a.created_at) }, { header: 'Action', cell: (a) => <code className="text-xs">{a.action}</code> },
          { header: 'Summary', cell: (a) => a.summary }, { header: 'Entity', cell: (a) => a.entity_type }]} />
      </Section>
    </PageContainer>
  )
}
