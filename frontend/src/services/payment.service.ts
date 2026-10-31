import type { Page, PageParams, Payment } from '@/types'
import { get, post } from './http'

type P = PageParams & Record<string, string | number | boolean | undefined>

export const paymentService = {
  list: (p?: P) => get<Page<Payment>>('/payments/', p),
  get: (id: string) => get<Payment>(`/payments/${id}/`),
  record: (b: unknown) => post<Payment>('/payments/', b),
  initiate: (b: { invoice_id: string; method?: string; amount?: string; idempotency_key?: string }) => post<Payment>('/payments/initiate/', b),
  razorpayConfig: () => get<{ enabled: boolean; mode: string; key_id: string | null; reason: string | null }>('/payments/razorpay/config/'),
  razorpayOrder: (b: { invoice_id: string; amount?: string; idempotency_key?: string }) =>
    post<{ payment_id: string; order_id: string; amount: number; currency: string; key_id: string; invoice_number: string; description: string }>('/payments/razorpay/orders/', b),
  razorpayVerify: (b: { payment_id: string; razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }) => post<Payment>('/payments/razorpay/verify/', b),
  simulate: (id: string, outcome: 'SUCCESS' | 'FAILED' | 'CANCELLED') => post<Payment>(`/payments/${id}/simulate/`, { outcome }),
}
