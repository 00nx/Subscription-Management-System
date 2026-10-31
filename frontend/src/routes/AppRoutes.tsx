import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'
import { LoadingState } from '@/components/shared/LoadingState'
import { StatusPage } from '@/components/shared/StatusPage'
import { HomeRedirect, ProtectedRoute, PublicOnlyRoute } from './ProtectedRoute'

const LoginPage = lazy(() => import('@/features/auth/LoginPage'))
const RegisterPage = lazy(() => import('@/features/auth/RegisterPage'))
const ForgotPasswordPage = lazy(() => import('@/features/auth/ForgotPasswordPage'))
const DashboardPage = lazy(() => import('@/features/dashboard/DashboardPage'))
const ProductsPage = lazy(() => import('@/features/products/ProductsPage'))
const ProductNewPage = lazy(() => import('@/features/products/ProductNewPage'))
const ProductDetailPage = lazy(() => import('@/features/products/ProductDetailPage'))
const PlansPage = lazy(() => import('@/features/plans/PlansPage'))
const SubscriptionsPage = lazy(() => import('@/features/subscriptions/SubscriptionsPage'))
const SubscriptionDetailPage = lazy(() => import('@/features/subscriptions/SubscriptionDetailPage'))
const QuotationsPage = lazy(() => import('@/features/quotations/QuotationsPage'))
const InvoicesPage = lazy(() => import('@/features/invoices/InvoicesPage'))
const PaymentsPage = lazy(() => import('@/features/payments/PaymentsPage'))
const DiscountsPage = lazy(() => import('@/features/discounts/DiscountsPage'))
const ReportsPage = lazy(() => import('@/features/reports/ReportsPage'))
const UsersPage = lazy(() => import('@/features/users/UsersPage'))
const SettingsPage = lazy(() => import('@/features/settings/SettingsPage'))
const CustomerDashboardPage = lazy(() => import('@/features/dashboard/CustomerDashboardPage'))
const CustomerSubscriptionsPage = lazy(() => import('@/features/subscriptions/CustomerSubscriptionsPage'))
const CustomerInvoicesPage = lazy(() => import('@/features/invoices/CustomerInvoicesPage'))
const ProfilePage = lazy(() => import('@/features/auth/ProfilePage'))

export function AppRoutes() {
  return (
    <Suspense fallback={<LoadingState />}>
      <Routes>
        <Route path="/" element={<HomeRedirect />} />

        <Route element={<PublicOnlyRoute />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        </Route>

        <Route element={<ProtectedRoute roles={['ADMIN', 'STAFF']} />}>
          <Route element={<AppLayout />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/products" element={<ProductsPage />} />
            <Route path="/products/new" element={<ProductNewPage />} />
            <Route path="/products/:id" element={<ProductDetailPage />} />
            <Route path="/plans" element={<PlansPage />} />
            <Route path="/subscriptions" element={<SubscriptionsPage />} />
            <Route path="/subscriptions/:id" element={<SubscriptionDetailPage />} />
            <Route path="/quotations" element={<QuotationsPage />} />
            <Route path="/invoices" element={<InvoicesPage />} />
            <Route path="/payments" element={<PaymentsPage />} />
            <Route path="/discounts" element={<DiscountsPage />} />
            <Route path="/reports" element={<ReportsPage />} />
            <Route path="/users" element={<UsersPage />} />
          </Route>
        </Route>

        <Route element={<ProtectedRoute roles={['ADMIN']} />}>
          <Route element={<AppLayout />}>
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Route>

        <Route element={<ProtectedRoute roles={['CUSTOMER']} />}>
          <Route element={<AppLayout />}>
            <Route path="/customer/dashboard" element={<CustomerDashboardPage />} />
            <Route path="/customer/subscriptions" element={<CustomerSubscriptionsPage />} />
            <Route path="/customer/invoices" element={<CustomerInvoicesPage />} />
            <Route path="/customer/profile" element={<ProfilePage />} />
          </Route>
        </Route>

        <Route path="/unauthorized" element={<StatusPage code="403" title="Unauthorized" description="You don't have access to this page." />} />
        <Route path="*" element={<StatusPage code="404" title="Page not found" description="The page you're looking for doesn't exist." />} />
      </Routes>
    </Suspense>
  )
}
