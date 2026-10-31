// Mirrors the backend schemas (backend/app/modules/*/schemas.py). Money and rates are decimal STRINGS ("999.00"): never use floats for finance.
export type BillingFrequency = 'DAILY' | 'WEEKLY' | 'MONTHLY' | 'YEARLY'
export type RecordStatus = 'ACTIVE' | 'INACTIVE' | 'ARCHIVED'
export type SubscriptionStatus = 'DRAFT' | 'QUOTATION' | 'CONFIRMED' | 'ACTIVE' | 'PAUSED' | 'EXPIRED' | 'CLOSED'
export type QuotationStatus = 'DRAFT' | 'QUOTATION' | 'CONFIRMED'
export type InvoiceStatus = 'DRAFT' | 'CONFIRMED' | 'PARTIALLY_PAID' | 'PAID' | 'CANCELLED'
export type PaymentStatus = 'PENDING' | 'SUCCESS' | 'FAILED' | 'CANCELLED'
export type PaymentMethod = 'CASH' | 'BANK_TRANSFER' | 'CARD' | 'UPI' | 'OTHER'
export type DiscountType = 'FIXED' | 'PERCENTAGE'

export interface Tax { id: string; name: string; rate: string; tax_type: string; description: string | null; applies_to: 'PRODUCTS' | 'ALL'; status: RecordStatus; created_at: string }
export interface VariantSnapshot { id: string; name: string; attribute: string; value: string; additional_price: string }
export interface TaxSnapshot { id?: string | null; name: string; rate: string; amount?: string }
export interface Variant { id: string; product_id: string; name: string; attribute_name: string; attribute_value: string; additional_price: string; status: RecordStatus }
export interface Product {
  id: string; name: string; product_type: string; sales_price: string; cost_price: string; description: string | null
  status: RecordStatus; tax_id: string | null; extra_tax_ids: string[]; variants: Variant[]; created_at: string; updated_at: string
}
export interface Plan {
  id: string; name: string; description: string | null; product_id: string; price: string; billing_frequency: BillingFrequency; min_quantity: number
  available_from: string | null; available_until: string | null; auto_close: boolean; allow_early_closure: boolean; allow_pause: boolean; allow_renewal: boolean
  status: RecordStatus; extra_product_ids: string[]; is_available: boolean; product_name: string
  variants: { id: string; name: string; attribute_name: string; attribute_value: string; additional_price: string }[]; created_at: string
}
export interface PublicPlan { id: string; name: string; description: string | null; price: string; billing_frequency: BillingFrequency; min_quantity: number; available_until: string | null; product_name: string }
export interface SubscribeResult { subscription: Subscription; invoice_id: string | null }
export interface Customer {
  id: string; customer_number: string; user_id: string; full_name: string; email: string; phone: string | null; company_name: string | null
  billing_address: string | null; tax_id: string | null; is_active: boolean; created_at: string
}
export interface SubLine { id: string; product_id: string; variant_id: string | null; description: string; quantity: number; unit_price: string; tax_id: string | null; tax_rate: string; variants: VariantSnapshot[]; taxes: TaxSnapshot[]; line_total: string }
export interface Subscription {
  id: string; number: string; customer_id: string; customer_name: string; plan_id: string; plan_name: string; quotation_id: string | null; status: SubscriptionStatus
  start_date: string; expiry_date: string | null; next_billing_date: string | null; billing_frequency: BillingFrequency; payment_terms_days: number
  term_periods: number | null; periods_billed: number; renewal_count: number; auto_renew: boolean; notes: string | null
  allow_pause: boolean; allow_renewal: boolean; allow_early_closure: boolean; renewal_opens: string | null
  subtotal: string; tax_total: string; total: string; lines: SubLine[]; created_at: string
}
export interface SubscriptionEvent { id: string; event_type: string; from_status: string | null; to_status: string | null; detail: string | null; actor_user_id: string | null; created_at: string }
export interface SubscriptionRequest { id: string; subscription_id: string; subscription_number: string; customer_id: string; request_type: 'CANCEL' | 'PAUSE' | 'RESUME'; status: string; reason: string | null; created_at: string; decided_at: string | null }
export interface LineInput { product_id: string; variant_id?: string | null; variant_ids?: string[]; quantity: number; unit_price?: string | null; description?: string | null }
export interface Quotation {
  id: string; number: string; customer_id: string; customer_name: string; template_id: string | null; plan_id: string; discount_id: string | null; status: QuotationStatus
  issue_date: string; expiry_date: string; is_expired: boolean; payment_terms_days: number; notes: string | null
  subtotal: string; discount_total: string; tax_total: string; total: string; lines: SubLine[]; subscription_id: string | null; sent_at: string | null; confirmed_at: string | null; created_at: string
}
export interface QuotationTemplate {
  id: string; name: string; plan_id: string | null; discount_id: string | null; validity_days: number; payment_terms_days: number; notes: string | null; terms: string | null; status: RecordStatus
  lines: { id: string; product_id: string; variant_id: string | null; variant_ids: string[]; quantity: number; unit_price: string | null }[]; created_at: string
}
export interface InvoiceLine { id: string; product_id: string | null; description: string; quantity: number; unit_price: string; line_subtotal: string; discount_amount: string; tax_rate: string; tax_amount: string; variants: VariantSnapshot[]; taxes: TaxSnapshot[]; line_total: string }
export interface Invoice {
  id: string; number: string; customer_id: string; customer_snapshot: Record<string, string | null>; subscription_id: string | null; subscription_number: string | null
  status: InvoiceStatus; source: string; period_start: string | null; period_end: string | null; issue_date: string; due_date: string; payment_terms_days: number; currency: string
  subtotal: string; discount_total: string; tax_total: string; total: string; amount_paid: string; outstanding: string; is_overdue: boolean; notes: string | null
  tax_breakdown: { name: string; rate: string; base: string; amount: string }[]; discount_breakdown: { name: string; amount: string }[]
  lines: InvoiceLine[]; created_at: string; confirmed_at: string | null
}
export interface PaymentTransaction { id: string; provider: string; provider_reference: string | null; event: string; status: string; message: string | null; created_at: string }
export interface Payment {
  id: string; invoice_id: string; invoice_number: string; customer_id: string; method: PaymentMethod; amount: string; status: PaymentStatus; payment_date: string | null
  transaction_reference: string | null; notes: string | null; provider: string; created_at: string; transactions: PaymentTransaction[]
}
export interface Discount {
  id: string; name: string; description: string | null; discount_type: DiscountType; value: string; min_purchase_amount: string; min_quantity: number
  start_date: string | null; end_date: string | null; max_usage: number | null; usage_count: number; is_active: boolean; product_ids: string[]; subscription_ids: string[]; created_at: string
}
export interface AppNotification { id: string; type: string; title: string; message: string; entity_type: string | null; entity_id: string | null; read_at: string | null; created_at: string }
export interface AuditLog { id: string; user_id: string | null; action: string; entity_type: string; entity_id: string; summary: string; changes: Record<string, unknown> | null; created_at: string }
export interface DueSubscription { id: string; number: string; customer_name: string; plan_name: string; status: SubscriptionStatus; next_billing_date: string | null; billing_frequency: BillingFrequency; total: string }
export interface BillingRunRecord { id: string; trigger: string; run_date: string; status: string; started_at: string; finished_at: string | null; batches: number; examined: number; invoiced: number; recovered: number; skipped_locked: number; failed: number; renewed: number; expired: number; failures: { subscription_id: string; error: string }[] }
export interface OverdueInvoice { id: string; number: string; customer_id: string; customer_name: string; customer_email: string; status: InvoiceStatus; issue_date: string; due_date: string; days_overdue: number; currency: string; total: string; amount_paid: string; outstanding: string; reminder_count: number; last_reminded_at: string | null; payments: { id: string; amount: string; method: string; payment_date: string | null }[] }
export interface EmailLog { id: string; to_email: string; subject: string; template: string; status: 'QUEUED' | 'SENT' | 'FAILED' | 'SUPPRESSED'; attempts: number; error: string | null; entity_type: string | null; entity_id: string | null; created_at: string; last_attempt_at: string | null; sent_at: string | null }
export interface BillingEvent { id: string; subscription_id: string; event_type: string; detail: string | null; created_at: string }

export interface DateRange { preset: string; date_from: string; date_to: string }
export interface Kpis { active_subscriptions: number; outstanding_amount: string; overdue_invoices: number; total_customers: number; mrr: string | null; arr: string | null; revenue_collected: string | null; total_invoices: number; revenue_billed: string | null; total_payments: string | null; payments_count: number | null }
export interface Dashboard {
  range: DateRange; kpis: Kpis; filters: Record<string, string | null>; active_by_plan: { plan: string; count: number }[]
  revenue_over_time: { period: string; amount: string }[] | null; mrr_trend: { period: string; amount: string }[] | null
  subscription_growth: { period: string; new: number; total: number }[]; subscription_status: { status: string; count: number }[]
  payment_status: { status: string; count: number; amount: string }[]; outstanding_vs_collected: { collected: string | null; outstanding: string }
  recent_activity: { type: string; title: string; detail: string; at: string }[]
}
export interface CustomerSummary { active_subscriptions: number; next_billing_date: string | null; outstanding_amount: string; recent_invoices: Invoice[]; recent_payments: Payment[] }
export interface ReportResult { summary: Record<string, any>; rows: { items: Record<string, any>[]; total: number; page: number; page_size: number } } // eslint-disable-line @typescript-eslint/no-explicit-any
