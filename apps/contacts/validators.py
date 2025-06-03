from decimal import Decimal
from django.core.exceptions import ValidationError
from apps.core.constants import CurrencyChoices, ValidationMessages


class PaymentValidator:
    """Centralized validation for agent payments"""

    @staticmethod
    def validate_payment_amounts(amount_uzs, amount_usd):
        """Validate payment amounts"""
        amount_uzs = amount_uzs or Decimal('0.00')
        amount_usd = amount_usd or Decimal('0.00')

        if amount_uzs < 0 or amount_usd < 0:
            raise ValidationError("Payment amount cannot be negative.")

        if amount_uzs == 0 and amount_usd == 0:
            raise ValidationError(ValidationMessages.PAYMENT_REQUIRED)

        if amount_uzs > 0 and amount_usd > 0:
            raise ValidationError(ValidationMessages.SINGLE_CURRENCY_ONLY)

        return amount_uzs, amount_usd

    @staticmethod
    def validate_currency_match(paid_to_account, amount_uzs, amount_usd):
        """Validate that payment currency matches account currency"""
        if not paid_to_account:
            raise ValidationError("Payment account is required.")

        payment_currency = CurrencyChoices.UZS if amount_uzs > 0 else CurrencyChoices.USD

        if paid_to_account.currency != payment_currency:
            raise ValidationError(
                ValidationMessages.CURRENCY_MISMATCH.format(
                    account_currency=paid_to_account.currency,
                    payment_currency=payment_currency
                )
            )

    @staticmethod
    def validate_agent_payment(agent, amount_uzs, amount_usd, paid_to_account):
        """Main validation method for agent payments"""
        if not agent:
            raise ValidationError("Agent is required.")

        amount_uzs, amount_usd = PaymentValidator.validate_payment_amounts(amount_uzs, amount_usd)
        PaymentValidator.validate_currency_match(paid_to_account, amount_uzs, amount_usd)

        return amount_uzs, amount_usd 