import type { Discount, Page, PageParams, Plan, Product, Tax, Variant, PublicPlan } from '@/types'
import { del, get, patch, post } from './http'

type P = PageParams & Record<string, string | number | boolean | undefined>

export const taxService = {
  list: (p?: P) => get<Page<Tax>>('/taxes/', p),
  create: (b: unknown) => post<Tax>('/taxes/', b),
  update: (id: string, b: unknown) => patch<Tax>(`/taxes/${id}/`, b),
}
export const productService = {
  list: (p?: P) => get<Page<Product>>('/products/', p),
  get: (id: string) => get<Product>(`/products/${id}/`),
  create: (b: unknown) => post<Product>('/products/', b),
  update: (id: string, b: unknown) => patch<Product>(`/products/${id}/`, b),
  archive: (id: string) => post<Product>(`/products/${id}/archive/`),
  remove: (id: string) => del(`/products/${id}/`),
  createVariant: (id: string, b: unknown) => post<Variant>(`/products/${id}/variants/`, b),
  updateVariant: (id: string, vid: string, b: unknown) => patch<Variant>(`/products/${id}/variants/${vid}/`, b),
  removeVariant: (id: string, vid: string) => del(`/products/${id}/variants/${vid}/`),
}
export const planService = {
  list: (p?: P) => get<Page<Plan>>('/plans/', p),
  public: () => get<PublicPlan[]>('/public/plans/'),
  create: (b: unknown) => post<Plan>('/plans/', b),
  update: (id: string, b: unknown) => patch<Plan>(`/plans/${id}/`, b),
}
export const discountService = {
  list: (p?: P) => get<Page<Discount>>('/discounts/', p),
  create: (b: unknown) => post<Discount>('/discounts/', b),
  update: (id: string, b: unknown) => patch<Discount>(`/discounts/${id}/`, b),
}
