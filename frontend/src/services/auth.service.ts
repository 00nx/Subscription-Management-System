import type { ApiEnvelope, LoginRequest, RegisterRequest, TokenResponse, User } from '@/types'
import { api, hasSessionCookie, refreshAccessToken, setAccessToken } from './api'

export const authService = {
  async register(body: RegisterRequest): Promise<User> {
    return (await api.post<ApiEnvelope<User>>('/auth/register/', body)).data.data
  },
  async login(body: LoginRequest): Promise<User> {
    const { data } = (await api.post<ApiEnvelope<TokenResponse>>('/auth/login/', body)).data
    setAccessToken(data.access_token)
    return data.user
  },
  async logout(): Promise<void> {
    await api.post('/auth/logout/')
  },
  async requestPasswordReset(email: string): Promise<string> {
    return (await api.post<ApiEnvelope<null>>('/auth/password-reset/', { email })).data.message
  },
  /** On page load: trade the refresh cookie for a new access token. Null when there is no session. */
  async restoreSession(): Promise<User | null> {
    if (!hasSessionCookie()) return null
    try {
      return (await refreshAccessToken()).user
    } catch {
      return null
    }
  },
}
