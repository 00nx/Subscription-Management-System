import type { ApiEnvelope, Page, PageParams, User } from '@/types'
import { api } from './api'

export const userService = {
  async list(params?: PageParams): Promise<Page<User>> {
    return (await api.get<ApiEnvelope<Page<User>>>('/users/', { params })).data.data
  },
}
