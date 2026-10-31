import { AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'

export function ErrorState({ message = 'Something went wrong', onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-center gap-2 p-12 text-center">
      <AlertCircle className="h-8 w-8 text-destructive" aria-hidden />
      <p className="text-sm">{message}</p>
      {onRetry && <Button variant="outline" size="sm" onClick={onRetry}>Try again</Button>}
    </div>
  )
}
