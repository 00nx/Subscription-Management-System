import { X } from 'lucide-react'
import { useEffect, useRef, type ReactNode } from 'react'
import { Button } from '@/components/ui/button'

interface Props { open: boolean; title: string; description?: string; onClose: () => void; children: ReactNode; wide?: boolean }

// Native <dialog>: focus trapping, Escape and the backdrop come from the browser.
export function Modal({ open, title, description, onClose, children, wide }: Props) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (open && !d.open) d.showModal?.()
    if (!open && d.open) d.close?.()
  }, [open])
  if (!open) return <dialog ref={ref} />
  return (
    <dialog ref={ref} onCancel={(e) => { e.preventDefault(); onClose() }} aria-labelledby="modal-title"
      className={`m-auto max-h-[90vh] w-[calc(100vw-2rem)] overflow-y-auto rounded-lg border border-border p-0 backdrop:bg-black/40 ${wide ? 'max-w-3xl' : 'max-w-lg'}`}>
      <div className="flex items-start justify-between gap-4 border-b border-border p-5">
        <div>
          <h2 id="modal-title" className="text-lg font-semibold">{title}</h2>
          {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
        </div>
        <Button variant="ghost" size="icon" aria-label="Close" onClick={onClose}><X className="h-4 w-4" /></Button>
      </div>
      <div className="p-5">{children}</div>
    </dialog>
  )
}
