import type { FieldValues, Path, UseFormSetError } from 'react-hook-form'
import { ApiError } from '@/services/api'

/** Puts backend validation errors on their fields; anything else goes to a form-level `root` error. */
export function applyServerError<T extends FieldValues>(err: unknown, setError: UseFormSetError<T>) {
  if (!(err instanceof ApiError)) return setError('root', { message: 'Unexpected error' })
  const entries = Object.entries(err.errors)
  entries.forEach(([field, msgs]) => setError(field as Path<T>, { message: msgs.join('. ') }))
  if (entries.length === 0) setError('root', { message: err.message })
}
