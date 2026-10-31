"""Import every module's models here so Alembic autogenerate sees them (env.py imports this file)."""
from app.modules.accounts.models import Notification, PasswordResetToken, RefreshToken, User, UserRole  # noqa: F401
from app.modules.analytics.models import AuditLog  # noqa: F401
from app.modules.billing.models import BillingRun, Tax  # noqa: F401
from app.modules.emails.models import EmailLog  # noqa: F401
from app.modules.customers.models import CustomerProfile  # noqa: F401
from app.modules.discounts.models import Discount, DiscountProduct, DiscountSubscription, DiscountUsage  # noqa: F401
from app.modules.invoices.models import Invoice, InvoiceLine  # noqa: F401
from app.modules.payments.models import Payment, PaymentTransaction  # noqa: F401
from app.modules.products.models import Product, ProductVariant  # noqa: F401
from app.modules.quotations.models import Quotation, QuotationLine, QuotationTemplate, QuotationTemplateLine  # noqa: F401
from app.modules.subscriptions.models import (PlanProduct, Subscription, SubscriptionEvent, SubscriptionLine,  # noqa: F401
                                              SubscriptionPlan, SubscriptionRequest)
