import type { FieldValues, Path, UseFormSetError } from 'react-hook-form'
import { ApiError } from '@/services/api'

const AUTH_FORM_FIELDS = ['email', 'password', 'full_name']

/**
 * Puts backend validation errors on their fields; anything else goes to a form-level `root` error.
 * `fieldNames` describes the fields rendered by the current form so errors for unregistered or
 * nested backend paths are surfaced instead of being silently dropped.
 */
export function applyServerError<T extends FieldValues>(
  err: unknown,
  setError: UseFormSetError<T>,
  fieldNames: readonly string[] = AUTH_FORM_FIELDS,
) {
  if (!(err instanceof ApiError)) return setError('root', { message: 'Unexpected error' })
  const known = new Set(fieldNames)
  const entries = Object.entries(err.errors)
  let unmapped = 0
  entries.forEach(([field, msgs]) => {
    if (known.has(field)) setError(field as Path<T>, { message: msgs.join('. ') })
    else unmapped += 1
  })
  if (entries.length === 0 || unmapped > 0) setError('root', { message: err.message })
}
