import { forwardRef, useId, type InputHTMLAttributes } from 'react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  error?: string
}

/** Label + input + error message. forwardRef so it works directly with react-hook-form's register(). */
export const FormField = forwardRef<HTMLInputElement, Props>(({ label, error, id, ...props }, ref) => {
  const auto = useId()
  const fieldId = id ?? auto
  return (
    <div className="space-y-1.5">
      <Label htmlFor={fieldId}>{label}</Label>
      <Input id={fieldId} ref={ref} aria-invalid={!!error} aria-describedby={error ? `${fieldId}-error` : undefined} {...props} />
      {error && <p id={`${fieldId}-error`} className="text-sm text-destructive">{error}</p>}
    </div>
  )
})
FormField.displayName = 'FormField'
