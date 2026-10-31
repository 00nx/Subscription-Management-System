from fastapi import APIRouter

from app.api.v1.endpoints import health
from app.modules.accounts.router import auth_router, notifications_router, users_router
from app.modules.analytics.reports import reports_router
from app.modules.analytics.router import analytics_router, audit_router
from app.modules.billing.router import billing_router, taxes_router
from app.modules.emails.router import router as emails_router
from app.modules.invoices.overdue import router as overdue_router
from app.modules.payments.router import webhook_router
from app.modules.invoices.router import router as invoices_router
from app.modules.payments.router import router as payments_router
from app.modules.customers.router import router as customers_router
from app.modules.discounts.router import router as discounts_router
from app.modules.products.router import router as products_router
from app.modules.quotations.router import router as quotations_router, templates_router
from app.modules.subscriptions.router import plans_router, public_router, requests_router, router as subscriptions_router

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(notifications_router)
api_router.include_router(customers_router)
api_router.include_router(audit_router)
api_router.include_router(taxes_router)
api_router.include_router(products_router)
api_router.include_router(discounts_router)
api_router.include_router(plans_router)
api_router.include_router(subscriptions_router)
api_router.include_router(public_router)
api_router.include_router(requests_router)
api_router.include_router(templates_router)
api_router.include_router(quotations_router)
api_router.include_router(billing_router)
api_router.include_router(invoices_router)
api_router.include_router(overdue_router)
api_router.include_router(webhook_router)
api_router.include_router(emails_router)
api_router.include_router(payments_router)
api_router.include_router(analytics_router)
api_router.include_router(reports_router)
