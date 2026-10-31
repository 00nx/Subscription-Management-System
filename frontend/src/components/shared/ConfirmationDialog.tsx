import { useEffect, useRef } from 'react'
import { Button } from '@/components/ui/button'

interface Props {
  open: boolean
  title: string
  description: string
  confirmLabel?: string
  destructive?: boolean
  onConfirm: () => void
  onCancel: () => void
}

// Native <dialog>: focus trapping, Escape and backdrop come from the browser.
export function ConfirmationDialog({ open, title, description, confirmLabel = 'Confirm', destructive, onConfirm, onCancel }: Props) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (open && !d.open) d.showModal?.()
    if (!open && d.open) d.close?.()
  }, [open])
  return (
    <dialog ref={ref} onCancel={onCancel} className="m-auto w-full max-w-md rounded-lg border border-border p-6 backdrop:bg-black/40">
      <h2 className="text-lg font-semibold">{title}</h2>
      <p className="mt-2 text-sm text-muted-foreground">{description}</p>
      <div className="mt-6 flex justify-end gap-2">
        <Button variant="outline" onClick={onCancel}>Cancel</Button>
        <Button variant={destructive ? 'destructive' : 'default'} onClick={onConfirm}>{confirmLabel}</Button>
      </div>
    </dialog>
  )
}
