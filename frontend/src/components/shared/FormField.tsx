import { forwardRef, useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

function Wrapper({ id, label, error, hint, children }: { id: string; label: string; error?: string; hint?: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint && !error && <p className="text-xs text-muted-foreground">{hint}</p>}
      {error && <p id={`${id}-error`} className="text-sm text-destructive">{error}</p>}
    </div>
  )
}

interface Props extends InputHTMLAttributes<HTMLInputElement> { label: string; error?: string; hint?: string }

/** Label + input + error message. forwardRef so it works directly with react-hook-form's register(). */
export const FormField = forwardRef<HTMLInputElement, Props>(({ label, error, hint, id, ...props }, ref) => {
  const auto = useId()
  const fieldId = id ?? auto
  return (
    <Wrapper id={fieldId} label={label} error={error} hint={hint}>
      <Input id={fieldId} ref={ref} aria-invalid={!!error} aria-describedby={error ? `${fieldId}-error` : undefined} {...props} />
    </Wrapper>
  )
})
FormField.displayName = 'FormField'

const controlClass = 'w-full rounded-md border border-border bg-card px-3 text-sm focus-visible:outline-2 focus-visible:outline-primary disabled:opacity-50 aria-[invalid=true]:border-destructive'

export const SelectField = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement> & { label: string; error?: string; hint?: string }>(
  ({ label, error, hint, id, children, className, ...props }, ref) => {
    const auto = useId()
    const fieldId = id ?? auto
    return (
      <Wrapper id={fieldId} label={label} error={error} hint={hint}>
        <select id={fieldId} ref={ref} aria-invalid={!!error} className={cn(controlClass, 'h-9', className)} {...props}>{children}</select>
      </Wrapper>
    )
  })
SelectField.displayName = 'SelectField'

export const TextAreaField = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string; error?: string; hint?: string }>(
  ({ label, error, hint, id, className, ...props }, ref) => {
    const auto = useId()
    const fieldId = id ?? auto
    return (
      <Wrapper id={fieldId} label={label} error={error} hint={hint}>
        <textarea id={fieldId} ref={ref} rows={3} aria-invalid={!!error} className={cn(controlClass, 'py-2', className)} {...props} />
      </Wrapper>
    )
  })
TextAreaField.displayName = 'TextAreaField'

export const CheckboxField = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { label: string }>(({ label, id, ...props }, ref) => {
  const auto = useId()
  const fieldId = id ?? auto
  return (
    <div className="flex items-center gap-2">
      <input id={fieldId} ref={ref} type="checkbox" className="h-4 w-4 rounded border-border accent-[var(--primary)]" {...props} />
      <Label htmlFor={fieldId} className="font-normal">{label}</Label>
    </div>
  )
})
CheckboxField.displayName = 'CheckboxField'
