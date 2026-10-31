import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { Plus } from 'lucide-react'
import { PageContainer } from '@/components/layout/PageContainer'
import { FilterDropdown } from '@/components/shared/FilterDropdown'
import { FormField, SelectField, CheckboxField } from '@/components/shared/FormField'
import { Modal } from '@/components/shared/Modal'
import { PageHeader } from '@/components/shared/PageHeader'
import { QueryTable } from '@/components/shared/QueryTable'
import { SearchInput } from '@/components/shared/SearchInput'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Toolbar } from '@/components/shared/Toolbar'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/hooks/useAuth'
import { useApiMutation } from '@/hooks/useApiMutation'
import { useListQuery } from '@/hooks/useListQuery'
import { useUrlState } from '@/hooks/useUrlState'
import { date } from '@/lib/format'
import { applyServerError, required } from '@/lib/forms'
import { queryKeys } from '@/lib/queryKeys'
import { emailSchema, passwordSchema } from '@/lib/validation'
import { userService } from '@/services/user.service'
import type { Role, User } from '@/types'

const createSchema = z.object({ full_name: required('Full name'), email: emailSchema, password: passwordSchema, role: z.enum(['ADMIN', 'STAFF', 'CUSTOMER']) })
type CreateValues = z.infer<typeof createSchema>
const ROLES: Role[] = ['ADMIN', 'STAFF', 'CUSTOMER']

function CreateUser({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { register, handleSubmit, reset, setError, formState: { errors } } = useForm<CreateValues>({ resolver: zodResolver(createSchema), defaultValues: { role: 'STAFF' } })
  const create = useApiMutation((v: CreateValues) => userService.create(v), { invalidate: [queryKeys.users.all, queryKeys.customers.all], success: 'User created', onSuccess: () => { reset(); onClose() } })
  return (
    <Modal open={open} onClose={onClose} title="Create user" description="Only administrators can create staff and admin accounts.">
      <form className="space-y-4" noValidate onSubmit={handleSubmit((v) => create.mutateAsync(v).catch((e) => applyServerError(e, setError)))}>
        <FormField label="Full name" error={errors.full_name?.message} {...register('full_name')} />
        <FormField label="Email" type="email" error={errors.email?.message} {...register('email')} />
        <FormField label="Temporary password" type="password" autoComplete="new-password" error={errors.password?.message} {...register('password')} />
        <SelectField label="Role" {...register('role')}>{ROLES.map((r) => <option key={r} value={r}>{r}</option>)}</SelectField>
        {errors.root && <p role="alert" className="text-sm text-destructive">{errors.root.message}</p>}
        <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button type="submit" disabled={create.isPending}>Create user</Button></div>
      </form>
    </Modal>
  )
}

const editSchema = z.object({ full_name: required('Full name'), role: z.enum(['ADMIN', 'STAFF', 'CUSTOMER']), is_active: z.boolean(), can_manage_discounts: z.boolean() })
type EditValues = z.infer<typeof editSchema>

function EditUser({ user, onClose }: { user: User | null; onClose: () => void }) {
  const { register, handleSubmit, setError, watch, formState: { errors } } = useForm<EditValues>({ resolver: zodResolver(editSchema), values: user ? { full_name: user.full_name, role: user.role, is_active: user.is_active, can_manage_discounts: !!user.can_manage_discounts } : undefined })
  const update = useApiMutation((v: EditValues) => userService.update(user!.id, v), { invalidate: [queryKeys.users.all, queryKeys.customers.all], success: 'User updated', onSuccess: onClose })
  return (
    <Modal open={!!user} onClose={onClose} title="Edit user" description={user?.email}>
      <form className="space-y-4" noValidate onSubmit={handleSubmit((v) => update.mutateAsync(v).catch((e) => applyServerError(e, setError)))}>
        <FormField label="Full name" error={errors.full_name?.message} {...register('full_name')} />
        <SelectField label="Role" {...register('role')}>{ROLES.map((r) => <option key={r} value={r}>{r}</option>)}</SelectField>
        <CheckboxField label="Account is active" {...register('is_active')} />
        {watch('role') === 'STAFF' && <CheckboxField label="Can create and edit discounts" {...register('can_manage_discounts')} />}
        {errors.root && <p role="alert" className="text-sm text-destructive">{errors.root.message}</p>}
        <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button type="submit" disabled={update.isPending}>Save</Button></div>
      </form>
    </Modal>
  )
}

export default function UsersPage() {
  const u = useUrlState()
  const { user: me } = useAuth()
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<User | null>(null)
  const params = { q: u.value('q'), role: u.value('role'), page: u.page, sort: '-created_at' }
  const query = useListQuery(queryKeys.users.list, userService.list, params)
  return (
    <PageContainer>
      <PageHeader title="Team" description="Staff, administrators and customer logins. Only administrators can add staff." actions={<Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" aria-hidden />New user</Button>} />
      <Toolbar>
        <SearchInput value={u.value('q')} onChange={(v) => u.set('q', v)} placeholder="Search name or email" />
        <FilterDropdown label="Role" value={u.value('role')} onChange={(v) => u.set('role', v)} options={ROLES.map((r) => ({ label: r, value: r }))} />
      </Toolbar>
      <QueryTable query={query} page={u.page} onPage={u.setPage} rowKey={(x) => x.id} emptyTitle="No users found" columns={[
        { header: 'Name', cell: (x) => x.full_name }, { header: 'Email', cell: (x) => x.email }, { header: 'Role', cell: (x) => <StatusBadge status={x.role} /> },
        { header: 'Status', cell: (x) => <StatusBadge status={x.is_active ? 'active' : 'inactive'} /> }, { header: 'Created', cell: (x) => date(x.created_at) },
        { header: '', cell: (x) => <Button variant="outline" size="sm" disabled={x.id === me?.id} title={x.id === me?.id ? 'You cannot edit your own role' : undefined} onClick={() => setEditing(x)}>Edit</Button> },
      ]} />
      <CreateUser open={creating} onClose={() => setCreating(false)} />
      <EditUser user={editing} onClose={() => setEditing(null)} />
    </PageContainer>
  )
}
