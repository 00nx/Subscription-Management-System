import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { FormField } from '@/components/shared/FormField'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/hooks/useAuth'
import { homeFor } from '@/routes/nav'
import { AuthLayout } from './AuthLayout'
import { loginSchema, type LoginValues } from './schemas'
import { applyServerError } from './useServerErrors'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const state = useLocation().state as { from?: string; registered?: boolean } | null
  const from = state?.from
  const { register, handleSubmit, setError, formState: { errors, isSubmitting } } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) })

  const onSubmit = handleSubmit(async (values) => {
    try {
      const user = await login(values)
      navigate(from ?? homeFor(user.role), { replace: true })
    } catch (err) {
      applyServerError(err, setError)
    }
  })

  return (
    <AuthLayout title="Log in" description="Welcome back. Enter your details to continue.">
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        {state?.registered && <p role="status" className="rounded-md bg-muted p-3 text-sm">Account created. Log in to continue.</p>}
        <FormField label="Email" type="email" autoComplete="email" error={errors.email?.message} {...register('email')} />
        <FormField label="Password" type="password" autoComplete="current-password" error={errors.password?.message} {...register('password')} />
        {errors.root && <p role="alert" className="text-sm text-destructive">{errors.root.message}</p>}
        <Button type="submit" className="w-full" disabled={isSubmitting}>{isSubmitting ? 'Logging in…' : 'Log in'}</Button>
        <div className="flex justify-between text-sm">
          <Link to="/forgot-password" className="text-primary hover:underline">Forgot password?</Link>
          <Link to="/register" className="text-primary hover:underline">Create account</Link>
        </div>
        <p className="text-center text-sm"><Link to="/pricing" className="text-primary hover:underline">See plans and pricing</Link></p>
      </form>
    </AuthLayout>
  )
}
