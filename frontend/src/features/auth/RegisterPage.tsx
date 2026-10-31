import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { FormField } from '@/components/shared/FormField'
import { Button } from '@/components/ui/button'
import { authService } from '@/services/auth.service'
import { AuthLayout } from './AuthLayout'
import { registerSchema, type RegisterValues } from './schemas'
import { applyServerError } from './useServerErrors'

export default function RegisterPage() {
  const navigate = useNavigate()
  const plan = useSearchParams()[0].get('plan')
  const { register, handleSubmit, setError, formState: { errors, isSubmitting } } = useForm<RegisterValues>({ resolver: zodResolver(registerSchema) })

  const onSubmit = handleSubmit(async (values) => {
    try {
      await authService.register(values)
      // after logging in, a visitor who picked a plan on the pricing page lands on that plan's subscribe dialog
      navigate('/login', { replace: true, state: { registered: true, from: plan ? `/customer/plans?subscribe=${plan}` : undefined } })
    } catch (err) {
      applyServerError(err, setError)
    }
  })

  return (
    <AuthLayout title="Create account" description="Sign up for a customer account.">
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        <FormField label="Full name" autoComplete="name" error={errors.full_name?.message} {...register('full_name')} />
        <FormField label="Email" type="email" autoComplete="email" error={errors.email?.message} {...register('email')} />
        <FormField label="Password" type="password" autoComplete="new-password" error={errors.password?.message} {...register('password')} />
        <FormField label="Confirm password" type="password" autoComplete="new-password" error={errors.confirm_password?.message} {...register('confirm_password')} />
        {errors.root && <p role="alert" className="text-sm text-destructive">{errors.root.message}</p>}
        <Button type="submit" className="w-full" disabled={isSubmitting}>{isSubmitting ? 'Creating…' : 'Create account'}</Button>
        <p className="text-center text-sm text-muted-foreground"><Link to="/pricing" className="text-primary hover:underline">See plans and pricing</Link></p>
        <p className="text-center text-sm">Already registered? <Link to="/login" className="text-primary hover:underline">Log in</Link></p>
      </form>
    </AuthLayout>
  )
}
