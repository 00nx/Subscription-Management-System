import type { ApiEnvelope, Payment, Page, PageParams } from '@/types'
import { api } from './api'

// Phase 2: the module owner adds the remaining CRUD calls and real types here.
export const paymentService = {
  async list(params?: PageParams): Promise<Page<Payment>> {
    return (await api.get<ApiEnvelope<Page<Payment>>>('/payments/', { params })).data.data
  },
}
