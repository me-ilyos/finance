from django.db import models


class CurrencyChoices(models.TextChoices):
    """Centralized currency choices for the entire application"""
    UZS = 'UZS', 'Uzbek Som'
    USD = 'USD', 'US Dollar'


class AccountTypeChoices(models.TextChoices):
    """Account type choices for financial accounts"""
    CASH_UZS = 'CASH_UZS', 'Cash (UZS)'
    CASH_USD = 'CASH_USD', 'Cash (USD)'
    CARD_UZS = 'CARD_UZS', 'Card (UZS)'
    CARD_USD = 'CARD_USD', 'Card (USD)'
    BANK_UZS = 'BANK_UZS', 'Bank Account (UZS)'
    BANK_USD = 'BANK_USD', 'Bank Account (USD)'


class TicketTypeChoices(models.TextChoices):
    """Ticket type choices for inventory management"""
    AIR_TICKET = 'AIR_TICKET', 'Air Ticket'
    TOUR_TICKET = 'TOUR_TICKET', 'Tour Ticket'


class PaymentType:
    """Constants for payment types"""
    AUTO_INITIAL = 'AUTO_INITIAL'
    MANUAL = 'MANUAL'


class ValidationMessages:
    """Standardized validation messages"""
    CURRENCY_MISMATCH = "Currency mismatch: account uses {account_currency}, payment uses {payment_currency}."
    INSUFFICIENT_BALANCE = "Insufficient balance. Available: {available:,.2f} {currency}"
    PAYMENT_EXCEEDS_BALANCE = "Payment amount ({amount:,.0f} {currency}) cannot exceed sale balance ({balance:,.0f} {currency})."
    PAYMENT_REQUIRED = "Payment amount must be greater than zero."
    SINGLE_CURRENCY_ONLY = "Payment must be in exactly one currency (UZS or USD)."
    AGENT_SALE_MISMATCH = "Selected sale does not belong to this agent." 