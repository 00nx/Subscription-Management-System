import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Modal } from '@/components/shared/Modal'
import { VariantChecks } from '@/components/shared/VariantChecks'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useApiMutation } from '@/hooks/useApiMutation'
import { FREQUENCY_LABEL, money } from '@/lib/format'
import { queryKeys } from '@/lib/queryKeys'
import { subscriptionService } from '@/services/sales.service'
import type { Plan } from '@/types'

/** A customer subscribes themselves: pick quantity and options, see the price, confirm. The backend creates, confirms and activates it
 *  and (when it starts today) issues the first invoice, so we go straight to that invoice to pay. */
export function SubscribeDialog({ plan, onClose }: { plan: Plan | null; onClose: () => void }) {
  const navigate = useNavigate()
  const [qty, setQty] = useState<string | null>(null)
  const [variantIds, setVariantIds] = useState<string[]>([])
  const [autoRenew, setAutoRenew] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const quantity = Math.max(Number(qty ?? plan?.min_quantity ?? 1) || 1, 1)
  const extra = plan ? plan.variants.filter((v) => variantIds.includes(v.id)).reduce((s, v) => s + Number(v.additional_price), 0) : 0
  const unit = plan ? Number(plan.price) + extra : 0
  const reset = () => { setQty(null); setVariantIds([]); setAutoRenew(false); setError(null) }
  const subscribe = useApiMutation(() => subscriptionService.subscribe({ plan_id: plan!.id, quantity, variant_ids: variantIds, auto_renew: autoRenew }), {
    invalidate: [queryKeys.subscriptions.all, queryKeys.invoices.all, queryKeys.summary, queryKeys.notifications.all], success: 'You are subscribed',
    onSuccess: (r) => { reset(); onClose(); navigate(r.invoice_id ? `/customer/invoices/${r.invoice_id}` : `/customer/subscriptions/${r.subscription.id}`) },
  })
  const close = () => { reset(); onClose() }
  return (
    <Modal open={!!plan} onClose={close} title={plan ? `Subscribe to ${plan.name}` : ''} description={plan ? `${money(plan.price)} per ${FREQUENCY_LABEL[plan.billing_frequency].toLowerCase()} billing` : undefined}>
      {plan && (
        <div className="space-y-4">
          <label className="block text-sm font-medium">Quantity
            <Input className="mt-1.5" inputMode="numeric" aria-label="Quantity" value={qty ?? String(plan.min_quantity)} onChange={(e) => setQty(e.target.value)} />
            <span className="mt-1 block text-xs font-normal text-muted-foreground">Minimum {plan.min_quantity}</span></label>
          {plan.variants.length > 0 && <div className="space-y-1"><span className="text-sm font-medium">Options</span><VariantChecks variants={plan.variants} value={variantIds} onChange={setVariantIds} /></div>}
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={autoRenew} onChange={(e) => setAutoRenew(e.target.checked)} />Renew automatically at the end of the term</label>
          <p className="rounded-md bg-muted/50 p-3 text-sm">Estimated per period: <strong>{money(unit * quantity)}</strong> <span className="text-muted-foreground">(taxes added on the invoice)</span><br />
            Your first invoice is issued today and you can pay it right away.</p>
          {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={close}>Cancel</Button>
            <Button type="button" disabled={subscribe.isPending} onClick={() => subscribe.mutateAsync().catch((e) => { setError(e instanceof Error ? e.message : 'Could not subscribe')})}>{subscribe.isPending ? 'Subscribing…' : 'Subscribe'}</Button>
          </div>
        </div>)}
    </Modal>
  )
}
