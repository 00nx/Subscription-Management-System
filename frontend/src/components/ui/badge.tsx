import { cva, type VariantProps } from 'class-variance-authority'
import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

export const badgeVariants = cva('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium', {
  variants: {
    variant: {
      default: 'bg-muted text-foreground',
      success: 'bg-success/10 text-success',
      warning: 'bg-warning/10 text-warning',
      destructive: 'bg-destructive/10 text-destructive',
      info: 'bg-primary/10 text-primary',
    },
  },
  defaultVariants: { variant: 'default' },
})

export const Badge = ({ className, variant, ...props }: HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) => (
  <span className={cn(badgeVariants({ variant }), className)} {...props} />
)
