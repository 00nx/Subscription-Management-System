import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { FormField, SelectField, TextAreaField } from '@/components/shared/FormField'
import { Modal } from '@/components/shared/Modal'
import { Button } from '@/components/ui/button'
import { useApiMutation } from '@/hooks/useApiMutation'
import { label, money } from '@/lib/format'
import { applyServerError, moneyField, required } from '@/lib/forms'
import { queryKeys } from '@/lib/queryKeys'
import { invoiceService } from '@/services/invoice.service'
import { paymentService } from '@/services/payment.service'
import type { Invoice } from '@/types'

const METHODS = ['CASH', 'BANK_TRANSFER', 'CARD', 'UPI', 'OTHER']
const schema = z.object({ invoice_id: required('Invoice'), method: z.enum(['CASH', 'BANK_TRANSFER', 'CARD', 'UPI', 'OTHER']), amount: moneyField('Amount').refine((v) => Number(v) > 0, 'Amount must be greater than zero'), transaction_reference: z.string(), notes: z.string() })
type Values = z.infer<typeof schema>

/** Staff record money received outside the system against an outstanding invoice (the backend rejects overpayment and duplicates). */
export function RecordPaymentDialog({ open, onClose, invoice }: { open: boolean; onClose: () => void; invoice?: Invoice }) {
  const payable = useQuery({ queryKey: queryKeys.invoices.list({ payable: true }), queryFn: () => invoiceService.list({ payable: true, page_size: 100 }), enabled: open && !invoice })
  const { register, handleSubmit, reset, watch, setValue, setError, formState: { errors } } = useForm<Values>({
    resolver: zodResolver(schema), values: { invoice_id: invoice?.id ?? '', method: 'BANK_TRANSFER', amount: invoice?.outstanding ?? '', transaction_reference: '', notes: '' },
  })
  const chosen = invoice ?? payable.data?.items.find((i) => i.id === watch('invoice_id'))
  const save = useApiMutation((v: Values) => paymentService.record({ ...v, transaction_reference: v.transaction_reference || null, notes: v.notes || null }),
    { invalidate: [queryKeys.payments.all, queryKeys.invoices.all, queryKeys.notifications.all], success: 'Payment recorded', onSuccess: () => { reset(); onClose() } })
  return (
    <Modal open={open} onClose={onClose} title="Record payment" description="Money received outside the system. Overpayment is rejected.">
      <form className="space-y-4" noValidate onSubmit={handleSubmit((v) => save.mutateAsync(v).catch((e) => applyServerError(e, setError)))}>
        {invoice ? <p className="text-sm">Invoice <strong>{invoice.number}</strong>: outstanding {money(invoice.outstanding)}</p> : (
          <SelectField label="Invoice" error={errors.invoice_id?.message} {...register('invoice_id', { onChange: (e) => { const i = payable.data?.items.find((x) => x.id === e.target.value); if (i) setValue('amount', i.outstanding) } })}>
            <option value="">Select an outstanding invoice…</option>{payable.data?.items.map((i) => <option key={i.id} value={i.id}>{i.number} · {i.customer_snapshot.name} · due {money(i.outstanding)}</option>)}
          </SelectField>)}
        {chosen && !invoice && <p className="text-sm text-muted-foreground">Amount due: {money(chosen.outstanding)}</p>}
        <div className="grid grid-cols-2 gap-3">
          <FormField label="Amount" inputMode="decimal" error={errors.amount?.message} {...register('amount')} />
          <SelectField label="Method" {...register('method')}>{METHODS.map((m) => <option key={m} value={m}>{label(m)}</option>)}</SelectField>
        </div>
        <FormField label="Transaction reference" hint="Must be unique: guards against recording the same payment twice." {...register('transaction_reference')} />
        <TextAreaField label="Notes" {...register('notes')} />
        {errors.root && <p role="alert" className="text-sm text-destructive">{errors.root.message}</p>}
        <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button type="submit" disabled={save.isPending}>Record payment</Button></div>
      </form>
    </Modal>
  )
}
