import type { ApiEnvelope, Subscription, Page, PageParams } from '@/types'
import { api } from './api'

// Phase 2: the module owner adds the remaining CRUD calls and real types here.
export const subscriptionService = {
  async list(params?: PageParams): Promise<Page<Subscription>> {
    return (await api.get<ApiEnvelope<Page<Subscription>>>('/subscriptions/', { params })).data.data
  },
}
