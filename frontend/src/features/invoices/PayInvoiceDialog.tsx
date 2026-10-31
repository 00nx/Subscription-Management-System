import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { FormField, SelectField } from '@/components/shared/FormField'
import { Modal } from '@/components/shared/Modal'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Button } from '@/components/ui/button'
import { useApiMutation } from '@/hooks/useApiMutation'
import { money } from '@/lib/format'
import { applyServerError, moneyField } from '@/lib/forms'
import { queryKeys } from '@/lib/queryKeys'
import { loadRazorpay } from '@/lib/razorpay'
import { paymentService } from '@/services/payment.service'
import type { Invoice, Payment } from '@/types'

const schema = z.object({ amount: moneyField('Amount').refine((v) => Number(v) > 0, 'Amount must be greater than zero'), method: z.enum(['CARD', 'UPI']) })
type Values = z.infer<typeof schema>

/** Step 1 initiates a payment; step 2 is the SIMULATED gateway. The gateway outcome is decided and recorded by the backend; this UI only shows what it returns. */
export function PayInvoiceDialog({ invoice, open, onClose }: { invoice: Invoice; open: boolean; onClose: () => void }) {
  const [payment, setPayment] = useState<Payment | null>(null)
  const [key, setKey] = useState(() => crypto.randomUUID())
  const rzConfig = useQuery({ queryKey: ['payments', 'razorpay-config'], queryFn: () => paymentService.razorpayConfig(), enabled: open, staleTime: 5 * 60_000 })
  const [rzError, setRzError] = useState<string | null>(null)
  const [rzBusy, setRzBusy] = useState(false)
  const [rzOpen, setRzOpen] = useState(false) // Razorpay's popup is showing: hide our dialog, which would otherwise sit on top of it (native dialogs live in the browser's top layer)
  const poll = useRef<ReturnType<typeof setInterval>>(undefined)
  useEffect(() => () => clearInterval(poll.current), [])
  const done = ['invoices', 'payments', 'notifications', 'customers'].map((k) => [k])
  const { register, handleSubmit, setError, formState: { errors } } = useForm<Values>({ resolver: zodResolver(schema), values: { amount: invoice.outstanding, method: 'CARD' } })
  const initiate = useApiMutation((v: Values) => paymentService.initiate({ invoice_id: invoice.id, amount: v.amount, method: v.method, idempotency_key: key }), { onSuccess: setPayment })
  const simulate = useApiMutation((o: 'SUCCESS' | 'FAILED' | 'CANCELLED') => paymentService.simulate(payment!.id, o), {
    invalidate: [...done, queryKeys.invoices.all], onSuccess: (p) => setPayment(p),
  })
  // After Checkout the backend confirms with Razorpay itself; if that is still pending, the signed webhook settles it. Poll until final.
  const watch = (id: string) => {
    let tries = 0
    clearInterval(poll.current)
    poll.current = setInterval(async () => {
      tries += 1
      try {
        const p = await paymentService.get(id)
        if (p.status !== 'PENDING' || tries >= 20) { clearInterval(poll.current); setPayment(p); setRzBusy(false) }
      } catch { clearInterval(poll.current); setRzBusy(false) }
    }, 2000)
  }
  const payWithRazorpay = async (v: Values) => {
    setRzError(null)
    setRzBusy(true)
    try {
      const o = await paymentService.razorpayOrder({ invoice_id: invoice.id, amount: v.amount, idempotency_key: key })
      const Razorpay = await loadRazorpay()
      setRzOpen(true)
      new Razorpay({
        key: o.key_id, amount: o.amount, currency: o.currency, order_id: o.order_id, name: 'Brightloop', description: o.description, theme: { color: '#4f46e5' },
        handler: async (r) => {
          setRzOpen(false)
          try {
            const p = await paymentService.razorpayVerify({ payment_id: o.payment_id, ...r })
            setPayment(p)
            if (p.status === 'PENDING') watch(p.id); else setRzBusy(false)
          } catch (e) { setRzError(e instanceof Error ? e.message : 'Could not verify the payment'); setRzBusy(false) }
        },
        modal: { ondismiss: () => { setRzOpen(false); setRzBusy(false) } },
      }).open()
    } catch (e) {
      setRzError(e instanceof Error ? e.message : 'Could not start Razorpay'); setRzOpen(false); setRzBusy(false)
    }
  }
  const close = () => { clearInterval(poll.current); setRzError(null); setRzOpen(false); setRzBusy(false); setPayment(null); setKey(crypto.randomUUID()); onClose() }

  const final = payment && payment.status !== 'PENDING'
  return (
    <Modal open={open && !rzOpen} onClose={close} title={`Pay invoice ${invoice.number}`} description={`Outstanding: ${money(invoice.outstanding, invoice.currency)}`}>
      {!payment ? (
        <form className="space-y-4" noValidate onSubmit={handleSubmit((v) => initiate.mutateAsync(v).catch((e) => applyServerError(e, setError)))}>
          <FormField label="Amount to pay" inputMode="decimal" hint="You can pay part of the balance." error={errors.amount?.message} {...register('amount')} />
          <SelectField label="Payment method" {...register('method')}><option value="CARD">Card</option><option value="UPI">UPI</option></SelectField>
          {errors.root && <p role="alert" className="text-sm text-destructive">{errors.root.message}</p>}
          {rzError && <p role="alert" className="text-sm text-destructive">{rzError}</p>}
          <div className="flex flex-wrap justify-end gap-2">
            <Button type="button" variant="outline" onClick={close}>Cancel</Button>
            {rzConfig.data?.enabled && <Button type="button" disabled={rzBusy} onClick={handleSubmit(payWithRazorpay)}>{rzBusy ? 'Opening Razorpay…' : 'Pay with Razorpay (test mode)'}</Button>}
            <Button type="submit" variant={rzConfig.data?.enabled ? 'outline' : 'default'} disabled={initiate.isPending}>{rzConfig.data?.enabled ? 'Use simulated gateway' : 'Continue to payment'}</Button>
          </div>
        </form>
      ) : payment.provider === 'RAZORPAY' ? (
        <div className="space-y-4">
          <div className="rounded-md border border-border bg-muted/50 p-4 text-sm">
            <p className="font-medium">Razorpay (test mode)</p>
            <dl className="mt-2 grid grid-cols-2 gap-1"><dt className="text-muted-foreground">Order</dt><dd>{payment.transaction_reference}</dd><dt className="text-muted-foreground">Amount</dt><dd>{money(payment.amount)}</dd>
              <dt className="text-muted-foreground">Status</dt><dd><StatusBadge status={payment.status} /></dd></dl>
          </div>
          <p role="status" className="text-sm">{payment.status === 'SUCCESS' ? 'Payment received and confirmed. Thank you!' : payment.status === 'PENDING' ? 'Payment submitted. Waiting for Razorpay to confirm it…' : 'The payment did not go through. You have not been charged.'}</p>
          <div className="flex justify-end"><Button onClick={close} disabled={payment.status === 'PENDING'}>Close</Button></div>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="rounded-md border border-border bg-muted/50 p-4 text-sm">
            <p className="font-medium">Test payment gateway</p>
            <p className="text-muted-foreground">This is a simulation: no real money moves and no card details are collected. Choose an outcome to test.</p>
            <dl className="mt-3 grid grid-cols-2 gap-1"><dt className="text-muted-foreground">Reference</dt><dd>{payment.transaction_reference}</dd><dt className="text-muted-foreground">Amount</dt><dd>{money(payment.amount)}</dd>
              <dt className="text-muted-foreground">Status</dt><dd><StatusBadge status={payment.status} /></dd></dl>
          </div>
          {final ? (
            <>
              <p role="status" className="text-sm">{payment.status === 'SUCCESS' ? 'Payment received. Thank you!' : payment.status === 'FAILED' ? 'The payment was declined. You have not been charged. You can try again.' : 'The payment was cancelled. You have not been charged.'}</p>
              <div className="flex justify-end"><Button onClick={close}>Close</Button></div>
            </>
          ) : (
            <div className="flex flex-wrap justify-end gap-2">
              <Button variant="outline" disabled={simulate.isPending} onClick={() => simulate.mutate('CANCELLED')}>Cancel payment</Button>
              <Button variant="destructive" disabled={simulate.isPending} onClick={() => simulate.mutate('FAILED')}>Decline</Button>
              <Button disabled={simulate.isPending} onClick={() => simulate.mutate('SUCCESS')}>Approve payment</Button>
            </div>)}
        </div>)}
    </Modal>
  )
}
