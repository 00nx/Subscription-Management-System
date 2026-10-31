import type { ApiEnvelope, Invoice, Page, PageParams } from '@/types'
import { api } from './api'

// Phase 2: the module owner adds the remaining CRUD calls and real types here.
export const invoiceService = {
  async list(params?: PageParams): Promise<Page<Invoice>> {
    return (await api.get<ApiEnvelope<Page<Invoice>>>('/invoices/', { params })).data.data
  },
}
