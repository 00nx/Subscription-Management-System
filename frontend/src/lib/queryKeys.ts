// One place for all TanStack Query keys: ['<resource>', '<kind>', ...params]. Invalidate by prefix.
const resource = (name: string) => ({
  all: [name] as const,
  list: (params?: object) => [name, 'list', params ?? {}] as const,
  detail: (id: string) => [name, 'detail', id] as const,
})

export const queryKeys = {
  auth: { me: ['auth', 'me'] as const },
  users: resource('users'),
  products: resource('products'),
  subscriptions: resource('subscriptions'),
  invoices: resource('invoices'),
  payments: resource('payments'),
}
