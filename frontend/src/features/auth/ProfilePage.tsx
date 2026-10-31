import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { PageContainer } from '@/components/layout/PageContainer'
import { ErrorState } from '@/components/shared/ErrorState'
import { FormField, TextAreaField } from '@/components/shared/FormField'
import { LoadingState } from '@/components/shared/LoadingState'
import { PageHeader } from '@/components/shared/PageHeader'
import { Section } from '@/components/shared/Section'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Button } from '@/components/ui/button'
import { useApiMutation } from '@/hooks/useApiMutation'
import { useAuth } from '@/hooks/useAuth'
import { applyServerError, required } from '@/lib/forms'
import { queryKeys } from '@/lib/queryKeys'
import { passwordSchema } from '@/lib/validation'
import { authService } from '@/services/auth.service'
import { customerService } from '@/services/sales.service'

const profileSchema = z.object({ full_name: required('Name'), phone: z.string(), company_name: z.string(), billing_address: z.string(), tax_id: z.string() })
type ProfileValues = z.infer<typeof profileSchema>
const pwSchema = z.object({ current_password: required('Current password'), new_password: passwordSchema, confirm_password: z.string() })
  .refine((v) => v.new_password === v.confirm_password, { path: ['confirm_password'], message: 'Passwords do not match' })
type PwValues = z.infer<typeof pwSchema>

function ChangePassword() {
  const { register, handleSubmit, reset, setError, formState: { errors } } = useForm<PwValues>({ resolver: zodResolver(pwSchema) })
  const change = useApiMutation((v: PwValues) => authService.changePassword(v.current_password, v.new_password), { success: 'Password changed', onSuccess: () => reset() })
  return (
    <Section title="Change password">
      <form className="grid max-w-md gap-4" noValidate onSubmit={handleSubmit((v) => change.mutateAsync(v).catch((e) => applyServerError(e, setError)))}>
        <FormField label="Current password" type="password" autoComplete="current-password" error={errors.current_password?.message} {...register('current_password')} />
        <FormField label="New password" type="password" autoComplete="new-password" error={errors.new_password?.message} {...register('new_password')} />
        <FormField label="Confirm new password" type="password" autoComplete="new-password" error={errors.confirm_password?.message} {...register('confirm_password')} />
        {errors.root && <p role="alert" className="text-sm text-destructive">{errors.root.message}</p>}
        <div><Button type="submit" disabled={change.isPending}>Change password</Button></div>
      </form>
    </Section>
  )
}

function CustomerProfileForm() {
  const query = useQuery({ queryKey: ['customers', 'me'], queryFn: customerService.me })
  const c = query.data
  const { register, handleSubmit, setError, formState: { errors, isDirty } } = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema), values: c ? { full_name: c.full_name, phone: c.phone ?? '', company_name: c.company_name ?? '', billing_address: c.billing_address ?? '', tax_id: c.tax_id ?? '' } : undefined,
  })
  const save = useApiMutation((v: ProfileValues) => customerService.updateMe(v), { invalidate: [['customers', 'me'], queryKeys.auth.me], success: 'Profile updated' })
  if (query.isLoading) return <LoadingState />
  if (!c) return <ErrorState message={query.error?.message} onRetry={() => query.refetch()} />
  return (
    <Section title="Personal and billing details">
      <form className="grid gap-4 sm:grid-cols-2" noValidate onSubmit={handleSubmit((v) => save.mutateAsync(v).catch((e) => applyServerError(e, setError)))}>
        <FormField label="Full name" error={errors.full_name?.message} {...register('full_name')} />
        <FormField label="Email" value={c.email} readOnly disabled />
        <FormField label="Phone" {...register('phone')} /><FormField label="Company" {...register('company_name')} /><FormField label="Tax ID" {...register('tax_id')} />
        <FormField label="Customer ID" value={c.customer_number} readOnly disabled />
        <div className="sm:col-span-2"><TextAreaField label="Billing address" {...register('billing_address')} /></div>
        {errors.root && <p role="alert" className="text-sm text-destructive sm:col-span-2">{errors.root.message}</p>}
        <div className="sm:col-span-2"><Button type="submit" disabled={!isDirty || save.isPending}>Save changes</Button></div>
      </form>
    </Section>
  )
}

export default function ProfilePage() {
  const { user } = useAuth()
  return (
    <PageContainer>
      <PageHeader title="Profile" description="Your account details." actions={user && <StatusBadge status={user.role} />} />
      {user?.role === 'CUSTOMER' ? <CustomerProfileForm /> : (
        <Section title="Account"><dl className="grid gap-3 text-sm sm:grid-cols-2"><div><dt className="text-muted-foreground">Name</dt><dd>{user?.full_name}</dd></div><div><dt className="text-muted-foreground">Email</dt><dd>{user?.email}</dd></div></dl></Section>)}
      <ChangePassword />
    </PageContainer>
  )
}
