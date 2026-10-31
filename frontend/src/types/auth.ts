export type Role = 'ADMIN' | 'STAFF' | 'CUSTOMER'

export interface User {
  id: string
  email: string
  full_name: string
  role: Role
  is_active: boolean
  can_manage_discounts?: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: User
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest extends LoginRequest {
  full_name: string
  confirm_password?: string
}
