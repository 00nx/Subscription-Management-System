/** Razorpay Standard Checkout loader. The script is fetched from Razorpay on demand, only when a customer chooses to pay with it. */
export interface RazorpayCheckoutOptions {
  key: string; amount: number; currency: string; order_id: string; name: string; description: string
  prefill?: { name?: string; email?: string }
  theme?: { color: string }
  handler: (r: { razorpay_payment_id: string; razorpay_order_id: string; razorpay_signature: string }) => void
  modal?: { ondismiss?: () => void }
}
interface RazorpayInstance { open(): void; on(event: string, cb: (r: { error?: { description?: string } }) => void): void }
declare global { interface Window { Razorpay?: new (o: RazorpayCheckoutOptions) => RazorpayInstance } }

const SRC = 'https://checkout.razorpay.com/v1/checkout.js'

export function loadRazorpay(): Promise<NonNullable<Window['Razorpay']>> {
  if (window.Razorpay) return Promise.resolve(window.Razorpay)
  return new Promise((resolve, reject) => {
    const s = document.createElement('script')
    s.src = SRC
    s.async = true
    s.onload = () => (window.Razorpay ? resolve(window.Razorpay) : reject(new Error('Razorpay Checkout did not load')))
    s.onerror = () => reject(new Error('Could not load Razorpay Checkout. Check your connection or ad blocker.'))
    document.body.appendChild(s)
  })
}
