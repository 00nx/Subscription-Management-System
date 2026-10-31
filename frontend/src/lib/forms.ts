import type { FieldValues, Path, UseFormSetError } from 'react-hook-form'
import { z } from 'zod'
import { ApiError } from '@/services/api'

/** Puts backend validation errors on their fields; anything else goes to a form-level `root` error. */
export function applyServerError<T extends FieldValues>(err: unknown, setError: UseFormSetError<T>) {
  if (!(err instanceof ApiError)) return setError('root', { message: 'Unexpected error' })
  const entries = Object.entries(err.errors)
  entries.forEach(([field, msgs]) => setError(field as Path<T>, { message: msgs.join('. ') }, { shouldFocus: false }))
  if (entries.length === 0) setError('root', { message: err.message })
}

// Form values stay strings (what inputs hold); these validate and the submit handler converts. Money is never a JS float.
export const moneyField = (label = 'Amount') => z.string().regex(/^\d+(\.\d{1,2})?$/, `${label}: enter a number with up to 2 decimals`)
export const optionalMoney = z.string().regex(/^(\d+(\.\d{1,2})?)?$/, 'Enter a number with up to 2 decimals')
export const intField = (min = 0, label = 'Value') => z.string().regex(/^\d+$/, `${label}: enter a whole number`).refine((v) => Number(v) >= min, `${label} must be at least ${min}`)
export const optionalInt = z.string().regex(/^\d*$/, 'Enter a whole number')
export const required = (label: string) => z.string().trim().min(1, `${label} is required`)
export const optionalDate = z.string()
