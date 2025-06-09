from django.db import models
from decimal import Decimal


class CurrencyChoices(models.TextChoices):
    """Centralized currency choices for the entire application"""
    UZS = 'UZS', 'Uzbek Som'
    USD = 'USD', 'US Dollar'


class AccountTypeChoices(models.TextChoices):
    """Account type choices for financial accounts"""
    CASH_UZS = 'CASH_UZS', 'Naqd (UZS)'
    CASH_USD = 'CASH_USD', 'Naqd (USD)'
    CARD_UZS = 'CARD_UZS', 'Karta (UZS)'
    CARD_USD = 'CARD_USD', 'Karta (USD)'
    BANK_UZS = 'BANK_UZS', 'Hisob raqam (UZS)'
    BANK_USD = 'BANK_USD', 'Hisob raqam (USD)'


class TicketTypeChoices(models.TextChoices):
    """Ticket type choices for inventory management"""
    AIR_TICKET = 'AIR_TICKET', 'Chipta'
    TOUR_TICKET = 'TOUR_TICKET', 'Tur paket'


class PaymentType:
    """Constants for payment types"""
    AUTO_INITIAL = 'AUTO_INITIAL'
    MANUAL = 'MANUAL'


class BusinessLimits:
    """Business rules and limits"""
    MAX_BALANCE_VALUE = Decimal('999999999.99')
    MIN_BALANCE_VALUE = Decimal('-999999999.99')


class ValidationMessages:
    """Standardized validation messages"""
    CURRENCY_MISMATCH = "Currency mismatch: account uses {account_currency}, payment uses {payment_currency}."
    INSUFFICIENT_BALANCE = "Insufficient balance. Available: {available:,.2f} {currency}"
    PAYMENT_EXCEEDS_BALANCE = "Payment amount ({amount:,.0f} {currency}) cannot exceed sale balance ({balance:,.0f} {currency})."
    PAYMENT_REQUIRED = "Payment amount must be greater than zero."
    SINGLE_CURRENCY_ONLY = "Payment must be in exactly one currency (UZS or USD)."
    AGENT_SALE_MISMATCH = "Selected sale does not belong to this agent." 