import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useSearchParams } from 'react-router-dom'
import { z } from 'zod'
import { FormField } from '@/components/shared/FormField'
import { Button } from '@/components/ui/button'
import { applyServerError } from '@/lib/forms'
import { passwordSchema } from '@/lib/validation'
import { authService } from '@/services/auth.service'
import { AuthLayout } from './AuthLayout'

const schema = z.object({ new_password: passwordSchema, confirm_password: z.string() }).refine((v) => v.new_password === v.confirm_password, { path: ['confirm_password'], message: 'Passwords do not match' })
type Values = z.infer<typeof schema>

export default function ResetPasswordPage() {
  const token = useSearchParams()[0].get('token') ?? ''
  const [done, setDone] = useState(false)
  const { register, handleSubmit, setError, formState: { errors, isSubmitting } } = useForm<Values>({ resolver: zodResolver(schema) })
  const onSubmit = handleSubmit(async (v) => {
    try { await authService.confirmPasswordReset(token, v.new_password); setDone(true) } catch (err) { applyServerError(err, setError) }
  })
  return (
    <AuthLayout title="Set a new password" description="Choose a strong password for your account.">
      {!token ? <p role="alert" className="text-sm text-destructive">This reset link is missing its token. Request a new one.</p> : done ? <p role="status" className="text-sm">Your password was updated. You can now log in.</p> : (
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          <FormField label="New password" type="password" autoComplete="new-password" error={errors.new_password?.message} {...register('new_password')} />
          <FormField label="Confirm password" type="password" autoComplete="new-password" error={errors.confirm_password?.message} {...register('confirm_password')} />
          {errors.root && <p role="alert" className="text-sm text-destructive">{errors.root.message}</p>}
          <Button type="submit" className="w-full" disabled={isSubmitting}>Update password</Button>
        </form>)}
      <p className="mt-4 text-center text-sm"><Link to="/login" className="text-primary hover:underline">Back to log in</Link>{!token || !done ? <> · <Link to="/forgot-password" className="text-primary hover:underline">Request a new link</Link></> : null}</p>
    </AuthLayout>
  )
}
