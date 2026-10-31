import type { Customer, CustomerSummary, LineInput, Page, PageParams, Quotation, QuotationTemplate, Subscription, SubscriptionEvent, SubscriptionRequest, SubscribeResult } from '@/types'
import { get, patch, post } from './http'

type P = PageParams & Record<string, string | number | boolean | undefined>

export const customerService = {
  list: (p?: P) => get<Page<Customer>>('/customers/', p),
  get: (id: string) => get<Customer>(`/customers/${id}/`),
  update: (id: string, b: unknown) => patch<Customer>(`/customers/${id}/`, b),
  me: () => get<Customer>('/customers/me/'),
  updateMe: (b: unknown) => patch<Customer>('/customers/me/', b),
  summary: () => get<CustomerSummary>('/customers/me/summary/'),
}
export const subscriptionService = {
  list: (p?: P) => get<Page<Subscription>>('/subscriptions/', p),
  get: (id: string) => get<Subscription>(`/subscriptions/${id}/`),
  create: (b: unknown) => post<Subscription>('/subscriptions/', b),
  subscribe: (b: { plan_id: string; quantity?: number; variant_ids?: string[]; auto_renew?: boolean; start_date?: string }) => post<SubscribeResult>('/subscriptions/subscribe/', b),
  update: (id: string, b: unknown) => patch<Subscription>(`/subscriptions/${id}/`, b),
  action: (id: string, name: 'confirm' | 'activate' | 'pause' | 'resume' | 'renew' | 'cancel') => post<Subscription>(`/subscriptions/${id}/${name}/`),
  events: (id: string) => get<SubscriptionEvent[]>(`/subscriptions/${id}/events/`),
  request: (id: string, request_type: string, reason?: string) => post<SubscriptionRequest>(`/subscriptions/${id}/requests/`, { request_type, reason }),
  requests: (p?: P) => get<Page<SubscriptionRequest>>('/subscription-requests/', p),
  decide: (id: string, approve: boolean) => post<SubscriptionRequest>(`/subscription-requests/${id}/${approve ? 'approve' : 'reject'}/`),
}
export const quotationService = {
  list: (p?: P) => get<Page<Quotation>>('/quotations/', p),
  get: (id: string) => get<Quotation>(`/quotations/${id}/`),
  create: (b: { customer_id: string; plan_id?: string; template_id?: string; discount_id?: string; validity_days?: number; payment_terms_days?: number; notes?: string; lines?: LineInput[] }) => post<Quotation>('/quotations/', b),
  update: (id: string, b: unknown) => patch<Quotation>(`/quotations/${id}/`, b),
  action: (id: string, name: 'send' | 'confirm') => post<Quotation>(`/quotations/${id}/${name}/`),
  convert: (id: string, b: { start_date?: string; term_periods?: number; auto_renew?: boolean }) => post<Subscription>(`/quotations/${id}/convert/`, b),
  templates: (p?: P) => get<Page<QuotationTemplate>>('/quotation-templates/', p),
  createTemplate: (b: unknown) => post<QuotationTemplate>('/quotation-templates/', b),
  updateTemplate: (id: string, b: unknown) => patch<QuotationTemplate>(`/quotation-templates/${id}/`, b),
}
