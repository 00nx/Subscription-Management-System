import type { DueSubscription, BillingEvent, BillingRunRecord, OverdueInvoice, Invoice, Page, PageParams } from '@/types'
import { download, get, post } from './http'

type P = PageParams & Record<string, string | number | boolean | undefined>

export const invoiceService = {
  list: (p?: P) => get<Page<Invoice>>('/invoices/', p),
  get: (id: string) => get<Invoice>(`/invoices/${id}/`),
  create: (b: unknown) => post<Invoice>('/invoices/', b),
  action: (id: string, name: 'confirm' | 'cancel' | 'send') => post<Invoice>(`/invoices/${id}/${name}/`),
  bulkConfirm: (ids: string[], send: boolean) => post<{ confirmed: number; sent: number; skipped: { id: string; reason: string }[] }>('/invoices/bulk-confirm/', { ids, send }),
  pdf: (inv: Pick<Invoice, 'id' | 'number'>, open = false) => download(`/invoices/${inv.id}/pdf/`, undefined, `${inv.number}.pdf`, open),
}
export const overdueService = {
  list: (p?: P) => get<Page<OverdueInvoice>>('/overdue-invoices/', p),
  remind: (ids: string[]) => post<{ reminded: number; skipped: { id: string; reason: string }[] }>('/overdue-invoices/remind/', { ids }),
}
export const billingService = {
  due: (p?: P) => get<Page<DueSubscription>>('/billing/due/', p),
  run: () => post<{ invoiced: number; failed: number; renewed: number; expired: number }>('/billing/run/'),
  failures: (p?: P) => get<Page<BillingEvent>>('/billing/failures/', p),
  runs: (p?: P) => get<Page<BillingRunRecord>>('/billing/runs/', p),
}
