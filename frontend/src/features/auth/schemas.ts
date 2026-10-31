import { z } from 'zod'
import { emailSchema, passwordSchema } from '@/lib/validation'

export const loginSchema = z.object({ email: emailSchema, password: z.string().min(1, 'Password is required') })
export const registerSchema = z.object({ full_name: z.string().trim().min(1, 'Full name is required'), email: emailSchema, password: passwordSchema, confirm_password: z.string() })
  .refine((v) => v.password === v.confirm_password, { path: ['confirm_password'], message: 'Passwords do not match' })
export const forgotPasswordSchema = z.object({ email: emailSchema })

export type LoginValues = z.infer<typeof loginSchema>
export type RegisterValues = z.infer<typeof registerSchema>
export type ForgotPasswordValues = z.infer<typeof forgotPasswordSchema>
