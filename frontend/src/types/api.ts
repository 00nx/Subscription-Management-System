export interface ApiEnvelope<T> {
  success: boolean
  message: string
  data: T
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface PageParams {
  page?: number
  page_size?: number
}
