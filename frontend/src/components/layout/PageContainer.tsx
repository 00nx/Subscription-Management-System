import type { ReactNode } from 'react'
import { Breadcrumbs } from './Breadcrumbs'

export function PageContainer({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 p-4 md:p-8">
      <Breadcrumbs />
      {children}
    </div>
  )
}
