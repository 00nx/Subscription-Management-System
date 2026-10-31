import type { ApiEnvelope, Product, Page, PageParams } from '@/types'
import { api } from './api'

// Phase 2: the module owner adds the remaining CRUD calls and real types here.
export const productService = {
  async list(params?: PageParams): Promise<Page<Product>> {
    return (await api.get<ApiEnvelope<Page<Product>>>('/products/', { params })).data.data
  },
}
