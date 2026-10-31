import { AxiosError, type AxiosAdapter, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { vi } from 'vitest'
import { api, ApiError, setAccessToken } from '@/services/api'
import { authService } from '@/services/auth.service'

const respond = (config: InternalAxiosRequestConfig, status: number, data: unknown): AxiosResponse => ({ data, status, statusText: '', headers: {}, config })
const fail = (config: InternalAxiosRequestConfig, status: number, data: unknown) =>
  Promise.reject(new AxiosError('failed', String(status), config, null, respond(config, status, data)))

const original = api.defaults.adapter
afterEach(() => { api.defaults.adapter = original; setAccessToken(null); document.cookie = 'csrf_token=; max-age=0' })

test('backend error envelopes become ApiError with message, status and field errors', async () => {
  api.defaults.adapter = ((c) => fail(c, 422, { success: false, message: 'Validation failed', errors: { email: ['bad'] } })) as AxiosAdapter
  const err = await api.get('/x').catch((e) => e)
  expect(err).toBeInstanceOf(ApiError)
  expect(err).toMatchObject({ message: 'Validation failed', status: 422, errors: { email: ['bad'] } })
})

test('network failures become ApiError with status 0', async () => {
  api.defaults.adapter = ((c) => Promise.reject(new AxiosError('Network Error', 'ERR_NETWORK', c))) as AxiosAdapter
  expect(await api.get('/x').catch((e) => e)).toMatchObject({ status: 0, message: expect.stringContaining('Network error') })
})

test('sends the bearer token once logged in', async () => {
  let auth: unknown
  api.defaults.adapter = (async (c) => { auth = c.headers.Authorization; return respond(c, 200, {}) }) as AxiosAdapter
  setAccessToken('abc')
  await api.get('/x')
  expect(auth).toBe('Bearer abc')
})

test('a 401 triggers one token refresh and replays the request', async () => {
  document.cookie = 'csrf_token=csrf123'
  const calls: string[] = []
  api.defaults.adapter = (async (c) => {
    calls.push(`${c.method} ${c.url} ${c.headers.Authorization ?? '-'}`)
    if (c.url === '/auth/refresh/') {
      expect(c.headers['X-CSRF-Token']).toBe('csrf123')
      return respond(c, 200, { data: { access_token: 'new', user: {} } })
    }
    return c.headers.Authorization === 'Bearer new' ? respond(c, 200, { data: 'ok' }) : fail(c, 401, { message: 'Not authenticated' })
  }) as AxiosAdapter
  setAccessToken('expired')
  expect((await api.get('/things')).data.data).toBe('ok')
  expect(calls).toEqual(['get /things Bearer expired', 'post /auth/refresh/ Bearer expired', 'get /things Bearer new'])
})

test('failed refresh signals session expiry', async () => {
  document.cookie = 'csrf_token=csrf123'
  api.defaults.adapter = ((c) => fail(c, 401, { message: 'Invalid refresh token' })) as AxiosAdapter
  const expired = vi.fn()
  window.addEventListener('auth:expired', expired)
  await expect(api.get('/things')).rejects.toMatchObject({ status: 401 })
  window.removeEventListener('auth:expired', expired)
  expect(expired).toHaveBeenCalledTimes(1)
})

test('restoreSession makes no request when there is no session cookie', async () => {
  const adapter = vi.fn()
  api.defaults.adapter = adapter as unknown as AxiosAdapter
  expect(await authService.restoreSession()).toBeNull()
  expect(adapter).not.toHaveBeenCalled()
})
