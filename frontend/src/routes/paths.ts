import type { Role } from '@/types'

/** Where a notification / activity item should take each kind of user. */
export function entityPath(role: Role, type: string | null, id: string | null): string | null {
  if (!type || !id) return null
  const customer = role === 'CUSTOMER'
  switch (type) {
    case 'invoice': return customer ? `/customer/invoices/${id}` : `/invoices/${id}`
    case 'subscription': return customer ? `/customer/subscriptions/${id}` : `/subscriptions/${id}`
    case 'payment': return customer ? '/customer/payments' : '/payments'
    case 'discount': return customer ? null : '/discounts'
    default: return null
  }
}
