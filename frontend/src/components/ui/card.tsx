import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

export const Card = ({ className, ...props }: HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('rounded-lg border border-border bg-card shadow-sm', className)} {...props} />
)
export const CardHeader = ({ className, ...props }: HTMLAttributes<HTMLDivElement>) => <div className={cn('space-y-1 p-6', className)} {...props} />
export const CardTitle = ({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) => <h2 className={cn('text-lg font-semibold', className)} {...props} />
export const CardDescription = ({ className, ...props }: HTMLAttributes<HTMLParagraphElement>) => <p className={cn('text-sm text-muted-foreground', className)} {...props} />
export const CardContent = ({ className, ...props }: HTMLAttributes<HTMLDivElement>) => <div className={cn('p-6 pt-0', className)} {...props} />
