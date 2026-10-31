import { AlertTriangle, BarChart3, Landmark, Bell, Contact, CreditCard, FileText, LayoutDashboard, Package, Percent, PlayCircle, Receipt, Repeat, Settings, Tag, UserCircle, Users, type LucideIcon } from 'lucide-react'
import type { Role } from '@/types'

export interface NavItem { label: string; to: string; icon: LucideIcon }

export const adminNav: NavItem[] = [
  { label: 'Dashboard', to: '/dashboard', icon: LayoutDashboard },
  { label: 'Customers', to: '/customers', icon: Contact },
  { label: 'Products', to: '/products', icon: Package },
  { label: 'Subscription Plans', to: '/plans', icon: Tag },
  { label: 'Subscriptions', to: '/subscriptions', icon: Repeat },
  { label: 'Quotations', to: '/quotations', icon: FileText },
  { label: 'Invoices', to: '/invoices', icon: Receipt },
  { label: 'Overdue', to: '/invoices/overdue', icon: AlertTriangle },
  { label: 'Billing', to: '/billing', icon: PlayCircle },
  { label: 'Payments', to: '/payments', icon: CreditCard },
  { label: 'Discounts', to: '/discounts', icon: Percent },
  { label: 'Taxes', to: '/taxes', icon: Landmark },
  { label: 'Reports', to: '/reports', icon: BarChart3 },
  { label: 'Team', to: '/team', icon: Users },
  { label: 'Settings', to: '/settings', icon: Settings },
]

export const customerNav: NavItem[] = [
  { label: 'Overview', to: '/customer/dashboard', icon: LayoutDashboard },
  { label: 'Plans', to: '/customer/plans', icon: Tag },
  { label: 'My Subscriptions', to: '/customer/subscriptions', icon: Repeat },
  { label: 'My Invoices', to: '/customer/invoices', icon: Receipt },
  { label: 'Payments', to: '/customer/payments', icon: CreditCard },
  { label: 'Notifications', to: '/customer/notifications', icon: Bell },
  { label: 'My Profile', to: '/customer/profile', icon: UserCircle },
]

// Staff see operations; Users and Settings are admin-only. Navigation only: FastAPI enforces the real rules.
const ADMIN_ONLY = new Set(['/team', '/settings'])
export const navFor = (role: Role): NavItem[] =>
  role === 'CUSTOMER' ? customerNav : role === 'ADMIN' ? adminNav : adminNav.filter((i) => !ADMIN_ONLY.has(i.to))

export const homeFor = (role: Role) => (role === 'CUSTOMER' ? '/customer/dashboard' : '/dashboard')

export const segmentLabels: Record<string, string> = {
  customer: 'Customer', dashboard: 'Dashboard', customers: 'Customers', products: 'Products', new: 'New', plans: 'Plans', subscriptions: 'Subscriptions', quotations: 'Quotations',
  templates: 'Templates', invoices: 'Invoices', overdue: 'Overdue', billing: 'Billing', payments: 'Payments', discounts: 'Discounts', reports: 'Reports', team: 'Team', taxes: 'Taxes', settings: 'Settings',
  profile: 'Profile', notifications: 'Notifications',
}
