import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import type { ApiEnvelope, TokenResponse } from '@/types'

export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1'

/** Standardised error: every failed request rejects with this, whatever the cause. */
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public errors: Record<string, string[]> = {},
  ) {
    super(message)
  }
}

type Cfg = InternalAxiosRequestConfig & { _retried?: boolean; skipAuthRefresh?: boolean }

// The access token lives in memory only; the refresh token is an HttpOnly cookie JS can't read.
let accessToken: string | null = null
export const setAccessToken = (t: string | null) => { accessToken = t }

const readCookie = (name: string) => document.cookie.split('; ').find((c) => c.startsWith(`${name}=`))?.split('=')[1]
export const hasSessionCookie = () => !!readCookie('csrf_token')

export const api = axios.create({ baseURL: API_URL, timeout: 10_000, withCredentials: true })

api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`
  const csrf = readCookie('csrf_token')
  if (csrf && config.method !== 'get') config.headers['X-CSRF-Token'] = csrf
  return config
})

let refreshing: Promise<TokenResponse> | null = null

/** Single-flight: concurrent 401s share one refresh, because refresh tokens rotate. */
export function refreshAccessToken(): Promise<TokenResponse> {
  refreshing ??= api
    .post<ApiEnvelope<TokenResponse>>('/auth/refresh/', null, { skipAuthRefresh: true } as Cfg)
    .then((r) => { setAccessToken(r.data.data.access_token); return r.data.data })
    .finally(() => { refreshing = null })
  return refreshing
}

function toApiError(err: unknown): ApiError {
  if (!(err instanceof AxiosError)) return new ApiError('Unexpected error', 0)
  if (!err.response) return new ApiError(err.code === 'ECONNABORTED' ? 'Request timed out' : 'Network error: cannot reach the server', 0)
  const body = err.response.data as Partial<ApiEnvelope<unknown>> & { errors?: Record<string, string[]> }
  return new ApiError(body?.message ?? err.message, err.response.status, body?.errors)
}

api.interceptors.response.use(undefined, async (err: unknown) => {
  const cfg = err instanceof AxiosError ? (err.config as Cfg | undefined) : undefined
  if (err instanceof AxiosError && err.response?.status === 401 && cfg && !cfg._retried && !cfg.skipAuthRefresh && hasSessionCookie()) {
    cfg._retried = true
    try {
      await refreshAccessToken()
      return api(cfg)
    } catch {
      setAccessToken(null)
      window.dispatchEvent(new Event('auth:expired'))
    }
  }
  // console.debug('api request failed', err)
  throw toApiError(err)
})
