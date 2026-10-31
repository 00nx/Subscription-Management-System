// One place for all TanStack Query keys: ['<resource>', '<kind>', ...params]. Invalidate by resource prefix (e.g. ['invoices']).
const resource = (name: string) => ({
  all: [name] as const,
  list: (params?: object) => [name, 'list', params ?? {}] as const,
  detail: (id: string) => [name, 'detail', id] as const,
})

export const queryKeys = {
  auth: { me: ['auth', 'me'] as const },
  users: resource('users'),
  customers: resource('customers'),
  products: resource('products'),
  taxes: resource('taxes'),
  plans: resource('plans'),
  discounts: resource('discounts'),
  subscriptions: resource('subscriptions'),
  requests: resource('subscription-requests'),
  quotations: resource('quotations'),
  templates: resource('quotation-templates'),
  invoices: resource('invoices'),
  payments: resource('payments'),
  notifications: resource('notifications'),
  billing: resource('billing'),
  audit: resource('audit'),
  analytics: { dashboard: (p?: object) => ['analytics', 'dashboard', p ?? {}] as const },
  reports: { get: (name: string, p?: object) => ['reports', name, p ?? {}] as const },
  summary: ['customers', 'summary'] as const,
}
