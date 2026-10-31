import type { AxiosRequestConfig } from 'axios'
import type { ApiEnvelope } from '@/types'
import { api } from './api'

type Params = Record<string, string | number | boolean | undefined | null>
const clean = (p?: Params) => (p ? Object.fromEntries(Object.entries(p).filter(([, v]) => v !== undefined && v !== null && v !== '')) : undefined)

export const get = async <T>(url: string, params?: Params, cfg?: AxiosRequestConfig) => (await api.get<ApiEnvelope<T>>(url, { params: clean(params), ...cfg })).data.data
export const post = async <T>(url: string, body?: unknown) => (await api.post<ApiEnvelope<T>>(url, body ?? {})).data.data
export const patch = async <T>(url: string, body: unknown) => (await api.patch<ApiEnvelope<T>>(url, body)).data.data
export const del = async (url: string) => { await api.delete(url) }

/** Authenticated file download (PDF/CSV): the bearer token can't ride on a plain <a href>, so fetch as a blob. */
export async function download(url: string, params: Params | undefined, filename: string, open = false) {
  const res = await api.get<Blob>(url, { params: clean(params), responseType: 'blob' })
  const href = URL.createObjectURL(res.data)
  if (open) window.open(href, '_blank')
  else {
    const a = document.createElement('a')
    a.href = href
    a.download = filename
    a.click()
  }
  setTimeout(() => URL.revokeObjectURL(href), 60_000)
}
