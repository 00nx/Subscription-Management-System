import { z } from 'zod'

// Mirrors backend/app/core/security.py:password_problems. The backend remains the authority.
export const passwordSchema = z
  .string()
  .min(9, 'Password must be more than 8 characters')
  .regex(/[A-Z]/, 'Password must contain an uppercase letter')
  .regex(/[a-z]/, 'Password must contain a lowercase letter')
  .regex(/[^A-Za-z0-9]/, 'Password must contain a special character')

export const emailSchema = z.string().min(1, 'Email is required').email('Enter a valid email address')
