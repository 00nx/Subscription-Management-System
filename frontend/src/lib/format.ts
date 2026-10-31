/** Money arrives as decimal strings; Intl formats the string without converting through float arithmetic for display only. */
export const money = (v: string | number | null | undefined, currency = 'INR') =>
  v == null ? '-' : new Intl.NumberFormat('en-IN', { style: 'currency', currency, minimumFractionDigits: 2 }).format(Number(v))

export const date = (v: string | null | undefined) => (v ? new Date(v.length === 10 ? v + 'T00:00:00' : v).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) : '-')
export const dateTime = (v: string | null | undefined) => (v ? new Date(v).toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '-')
export const label = (v: string) => v.toLowerCase().split('_').map((w) => w[0].toUpperCase() + w.slice(1)).join(' ')
export const FREQUENCY_LABEL: Record<string, string> = { DAILY: 'Daily', WEEKLY: 'Weekly', MONTHLY: 'Monthly', YEARLY: 'Yearly' }
