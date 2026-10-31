import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'
import { FormField } from '@/components/shared/FormField'
import { Button } from '@/components/ui/button'
import { authService } from '@/services/auth.service'
import { AuthLayout } from './AuthLayout'
import { forgotPasswordSchema, type ForgotPasswordValues } from './schemas'
import { applyServerError } from './useServerErrors'

export default function ForgotPasswordPage() {
  const [sent, setSent] = useState<string | null>(null)
  const { register, handleSubmit, setError, formState: { errors, isSubmitting } } = useForm<ForgotPasswordValues>({ resolver: zodResolver(forgotPasswordSchema) })

  const onSubmit = handleSubmit(async (values) => {
    try {
      setSent(await authService.requestPasswordReset(values.email))
    } catch (err) {
      applyServerError(err, setError, Object.keys(values))
    }
  })

  return (
    <AuthLayout title="Forgot password" description="We'll send reset instructions if the account exists.">
      {sent ? <p role="status" className="text-sm">{sent}</p> : (
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          <FormField label="Email" type="email" autoComplete="email" error={errors.email?.message} {...register('email')} />
          {errors.root && <p role="alert" className="text-sm text-destructive">{errors.root.message}</p>}
          <Button type="submit" className="w-full" disabled={isSubmitting}>Send reset link</Button>
        </form>
      )}
      <p className="mt-4 text-center text-sm"><Link to="/login" className="text-primary hover:underline">Back to log in</Link></p>
    </AuthLayout>
  )
}
