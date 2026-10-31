import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'
import { LoadingState } from '@/components/shared/LoadingState'
import { StatusPage } from '@/components/shared/StatusPage'
import { HomeRedirect, ProtectedRoute, PublicOnlyRoute } from './ProtectedRoute'

const LoginPage = lazy(() => import('@/features/auth/LoginPage'))
const RegisterPage = lazy(() => import('@/features/auth/RegisterPage'))
const ForgotPasswordPage = lazy(() => import('@/features/auth/ForgotPasswordPage'))
const ResetPasswordPage = lazy(() => import('@/features/auth/ResetPasswordPage'))
const ProfilePage = lazy(() => import('@/features/auth/ProfilePage'))
const NotificationsPage = lazy(() => import('@/features/notifications/NotificationsPage'))

const DashboardPage = lazy(() => import('@/features/dashboard/DashboardPage'))
const CustomersPage = lazy(() => import('@/features/customers/CustomersPage'))
const CustomerDetailPage = lazy(() => import('@/features/customers/CustomerDetailPage'))
const ProductsPage = lazy(() => import('@/features/products/ProductsPage'))
const ProductNewPage = lazy(() => import('@/features/products/ProductNewPage'))
const ProductDetailPage = lazy(() => import('@/features/products/ProductDetailPage'))
const PlansPage = lazy(() => import('@/features/plans/PlansPage'))
const SubscriptionsPage = lazy(() => import('@/features/subscriptions/SubscriptionsPage'))
const SubscriptionDetailPage = lazy(() => import('@/features/subscriptions/SubscriptionDetailPage'))
const QuotationsPage = lazy(() => import('@/features/quotations/QuotationsPage'))
const QuotationNewPage = lazy(() => import('@/features/quotations/QuotationNewPage'))
const QuotationDetailPage = lazy(() => import('@/features/quotations/QuotationDetailPage'))
const TemplatesPage = lazy(() => import('@/features/quotations/TemplatesPage'))
const InvoicesPage = lazy(() => import('@/features/invoices/InvoicesPage'))
const InvoiceDetailPage = lazy(() => import('@/features/invoices/InvoiceDetailPage'))
const OverdueInvoicesPage = lazy(() => import('@/features/invoices/OverdueInvoicesPage'))
const BillingPage = lazy(() => import('@/features/billing/BillingPage'))
const PaymentsPage = lazy(() => import('@/features/payments/PaymentsPage'))
const DiscountsPage = lazy(() => import('@/features/discounts/DiscountsPage'))
const ReportsPage = lazy(() => import('@/features/reports/ReportsPage'))
const UsersPage = lazy(() => import('@/features/users/UsersPage'))
const TaxesPage = lazy(() => import('@/features/taxes/TaxesPage'))
const SettingsPage = lazy(() => import('@/features/settings/SettingsPage'))

const PublicPlansPage = lazy(() => import('@/features/plans/PublicPlansPage'))
const CustomerDashboardPage = lazy(() => import('@/features/dashboard/CustomerDashboardPage'))
const CustomerPlansPage = lazy(() => import('@/features/plans/CustomerPlansPage'))
const CustomerSubscriptionsPage = lazy(() => import('@/features/subscriptions/CustomerSubscriptionsPage'))
const CustomerSubscriptionDetailPage = lazy(() => import('@/features/subscriptions/CustomerSubscriptionDetailPage'))
const CustomerInvoicesPage = lazy(() => import('@/features/invoices/CustomerInvoicesPage'))
const CustomerInvoiceDetailPage = lazy(() => import('@/features/invoices/CustomerInvoiceDetailPage'))
const CustomerPaymentsPage = lazy(() => import('@/features/payments/CustomerPaymentsPage'))

/** Route guards only shape navigation; every API call is authorised again by FastAPI. */
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
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/pricing" element={<PublicPlansPage />} />

        <Route element={<ProtectedRoute roles={['ADMIN', 'STAFF']} />}>
          <Route element={<AppLayout />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/customers" element={<CustomersPage />} />
            <Route path="/customers/:id" element={<CustomerDetailPage />} />
            <Route path="/products" element={<ProductsPage />} />
            <Route path="/products/:id" element={<ProductDetailPage />} />
            <Route path="/plans" element={<PlansPage />} />
            <Route path="/subscriptions" element={<SubscriptionsPage />} />
            <Route path="/subscriptions/:id" element={<SubscriptionDetailPage />} />
            <Route path="/quotations" element={<QuotationsPage />} />
            <Route path="/quotations/new" element={<QuotationNewPage />} />
            <Route path="/quotations/templates" element={<TemplatesPage />} />
            <Route path="/quotations/:id" element={<QuotationDetailPage />} />
            <Route path="/invoices" element={<InvoicesPage />} />
            <Route path="/invoices/overdue" element={<OverdueInvoicesPage />} />
            <Route path="/invoices/:id" element={<InvoiceDetailPage />} />
            <Route path="/billing" element={<BillingPage />} />
            <Route path="/payments" element={<PaymentsPage />} />
            <Route path="/discounts" element={<DiscountsPage />} />
            <Route path="/taxes" element={<TaxesPage />} />
            <Route path="/reports" element={<ReportsPage />} />
            <Route path="/notifications" element={<NotificationsPage />} />
            <Route path="/account" element={<ProfilePage />} />
          </Route>
        </Route>

        <Route element={<ProtectedRoute roles={['ADMIN']} />}>
          <Route element={<AppLayout />}>
            <Route path="/products/new" element={<ProductNewPage />} />
            <Route path="/team" element={<UsersPage />} />
            <Route path="/users" element={<Navigate to="/team" replace />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Route>

        <Route element={<ProtectedRoute roles={['CUSTOMER']} />}>
          <Route element={<AppLayout />}>
            <Route path="/customer/dashboard" element={<CustomerDashboardPage />} />
            <Route path="/customer/plans" element={<CustomerPlansPage />} />
            <Route path="/customer/subscriptions" element={<CustomerSubscriptionsPage />} />
            <Route path="/customer/subscriptions/:id" element={<CustomerSubscriptionDetailPage />} />
            <Route path="/customer/invoices" element={<CustomerInvoicesPage />} />
            <Route path="/customer/invoices/:id" element={<CustomerInvoiceDetailPage />} />
            <Route path="/customer/payments" element={<CustomerPaymentsPage />} />
            <Route path="/customer/notifications" element={<NotificationsPage />} />
            <Route path="/customer/profile" element={<ProfilePage />} />
          </Route>
        </Route>

        <Route path="/unauthorized" element={<StatusPage code="403" title="Unauthorized" description="You don't have access to this page." />} />
        <Route path="*" element={<StatusPage code="404" title="Page not found" description="The page you're looking for doesn't exist." />} />
      </Routes>
    </Suspense>
  )
}
