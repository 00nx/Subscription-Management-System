import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { CheckCircle2, XCircle } from 'lucide-react'

type Kind = 'success' | 'error'
interface Toast { id: number; kind: Kind; message: string }
interface ToastApi { success: (m: string) => void; error: (m: string) => void }

const ToastContext = createContext<ToastApi | null>(null)
let nextId = 1

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const push = useCallback((kind: Kind, message: string) => {
    const id = nextId++
    setToasts((t) => [...t, { id, kind, message }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === 'error' ? 7000 : 4000)
  }, [])
  const api = useMemo<ToastApi>(() => ({ success: (m) => push('success', m), error: (m) => push('error', m) }), [push])
  return (
    <ToastContext.Provider value={api}>
      {children}
      <div aria-live="polite" className="fixed bottom-4 right-4 z-50 flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2">
        {toasts.map((t) => (
          <div key={t.id} role={t.kind === 'error' ? 'alert' : 'status'} className="flex items-start gap-2 rounded-md border border-border bg-card p-3 text-sm shadow-md">
            {t.kind === 'success' ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden /> : <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden />}
            <span>{t.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>')
  return ctx
}
