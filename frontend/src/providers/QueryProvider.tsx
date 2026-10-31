import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ApiError } from '@/services/api'
import { useState, type ReactNode } from 'react'

export const makeQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: true,
        retry: (count, err) => !(err instanceof ApiError && err.status >= 400 && err.status < 500) && count < 2,
      },
    },
  })

export function QueryProvider({ children, client }: { children: ReactNode; client?: QueryClient }) {
  const [qc] = useState(() => client ?? makeQueryClient())
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}
