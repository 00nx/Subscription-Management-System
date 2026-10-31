import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'

/** List filters live in the URL (shareable, survives back/forward, and the header search can deep-link into them). Changing a filter resets to page 1. */
export function useUrlState(defaults: Record<string, string> = {}) {
  const [sp, setSp] = useSearchParams()
  const value = (key: string) => sp.get(key) ?? defaults[key] ?? ''
  const set = useCallback((key: string, v: string) => {
    setSp((prev) => {
      const next = new URLSearchParams(prev)
      if (v) next.set(key, v)
      else next.delete(key)
      if (key !== 'page') next.delete('page')
      return next
    }, { replace: true })
  }, [setSp])
  /** Several changes in ONE update. Calling set() repeatedly in a single handler loses all but the last (router updates aren't queued). */
  const setMany = useCallback((entries: Record<string, string>) => {
    setSp((prev) => {
      const next = new URLSearchParams(prev)
      for (const [k, v] of Object.entries(entries)) (v ? next.set(k, v) : next.delete(k))
      next.delete('page')
      return next
    }, { replace: true })
  }, [setSp])
  return { value, set, setMany, page: Number(sp.get('page') ?? 1) || 1, setPage: (p: number) => set('page', p > 1 ? String(p) : '') }
}
