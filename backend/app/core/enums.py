"""Shared status enums (stored as strings; see docs/DATABASE.md). One definition, imported by every module."""
import enum


class BillingFrequency(str, enum.Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"


class RecordStatus(str, enum.Enum):
    """Products, variants, plans, taxes."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"


class QuotationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    QUOTATION = "QUOTATION"  # sent to the customer
    CONFIRMED = "CONFIRMED"


class SubscriptionStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    QUOTATION = "QUOTATION"
    CONFIRMED = "CONFIRMED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    EXPIRED = "EXPIRED"
    CLOSED = "CLOSED"


class InvoiceStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    CANCELLED = "CANCELLED"  # "overdue" is derived (due_date + outstanding), never stored


class DiscountType(str, enum.Enum):
    FIXED = "FIXED"
    PERCENTAGE = "PERCENTAGE"


class PaymentMethod(str, enum.Enum):
    CASH = "CASH"
    BANK_TRANSFER = "BANK_TRANSFER"
    CARD = "CARD"
    UPI = "UPI"
    OTHER = "OTHER"


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
