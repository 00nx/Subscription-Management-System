import { BarChart3, CreditCard, FileText, LayoutDashboard, Package, Percent, Receipt, Repeat, Settings, Tag, UserCircle, Users, type LucideIcon } from 'lucide-react'
import type { Role } from '@/types'

export interface NavItem { label: string; to: string; icon: LucideIcon }

const STAFF_ROLES: Role[] = ['ADMIN', 'STAFF']

export const adminNav: NavItem[] = [
  { label: 'Dashboard', to: '/dashboard', icon: LayoutDashboard },
  { label: 'Products', to: '/products', icon: Package },
  { label: 'Plans', to: '/plans', icon: Tag },
  { label: 'Subscriptions', to: '/subscriptions', icon: Repeat },
  { label: 'Quotations', to: '/quotations', icon: FileText },
  { label: 'Invoices', to: '/invoices', icon: Receipt },
  { label: 'Payments', to: '/payments', icon: CreditCard },
  { label: 'Discounts', to: '/discounts', icon: Percent },
  { label: 'Reports', to: '/reports', icon: BarChart3 },
  { label: 'Users', to: '/users', icon: Users },
  { label: 'Settings', to: '/settings', icon: Settings },
]

export const customerNav: NavItem[] = [
  { label: 'Dashboard', to: '/customer/dashboard', icon: LayoutDashboard },
  { label: 'Subscriptions', to: '/customer/subscriptions', icon: Repeat },
  { label: 'Invoices', to: '/customer/invoices', icon: Receipt },
  { label: 'Profile', to: '/customer/profile', icon: UserCircle },
]

// Settings is admin-only; staff see everything else. Navigation only: FastAPI enforces the real rules.
export const navFor = (role: Role): NavItem[] =>
  role === 'CUSTOMER' ? customerNav : role === 'ADMIN' ? adminNav : adminNav.filter((i) => i.to !== '/settings')

export const homeFor = (role: Role) => (role === 'CUSTOMER' ? '/customer/dashboard' : '/dashboard')
export { STAFF_ROLES }

export const segmentLabels: Record<string, string> = {
  customer: 'Customer', dashboard: 'Dashboard', products: 'Products', new: 'New', plans: 'Plans', subscriptions: 'Subscriptions',
  quotations: 'Quotations', invoices: 'Invoices', payments: 'Payments', discounts: 'Discounts', reports: 'Reports',
  users: 'Users', settings: 'Settings', profile: 'Profile',
}
