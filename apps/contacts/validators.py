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
    def validate_related_sale(agent, related_sale, amount_uzs, amount_usd, payment_instance=None):
        """Validate related sale constraints"""
        if not related_sale:
            return

        # Check if sale belongs to agent
        if related_sale.agent != agent:
            raise ValidationError(ValidationMessages.AGENT_SALE_MISMATCH)

        # Determine payment currency and amount
        payment_currency = CurrencyChoices.UZS if amount_uzs > 0 else CurrencyChoices.USD
        payment_amount = amount_uzs if payment_currency == CurrencyChoices.UZS else amount_usd

        # Check currency match
        if related_sale.sale_currency != payment_currency:
            raise ValidationError(
                f"Sale currency ({related_sale.sale_currency}) must match payment currency ({payment_currency}). "
                f"You can only pay in {related_sale.sale_currency}."
            )

        # Check payment doesn't exceed balance
        available_balance = related_sale.balance_due_on_this_sale

        # For updates, add back the original contribution of this payment
        if payment_instance and payment_instance.pk:
            try:
                from .models import AgentPayment
                original_payment = AgentPayment.objects.get(pk=payment_instance.pk)
                if original_payment.related_sale_id == related_sale.id:
                    if related_sale.sale_currency == CurrencyChoices.UZS:
                        available_balance += original_payment.amount_paid_uzs
                    else:
                        available_balance += original_payment.amount_paid_usd
            except:
                pass

        if payment_amount > available_balance:
            raise ValidationError(
                ValidationMessages.PAYMENT_EXCEEDS_BALANCE.format(
                    amount=payment_amount,
                    currency=payment_currency,
                    balance=available_balance
                )
            )

    @staticmethod
    def validate_agent_payment(agent, amount_uzs, amount_usd, paid_to_account, related_sale=None, payment_instance=None):
        """Main validation method for agent payments"""
        if not agent:
            raise ValidationError("Agent is required.")

        amount_uzs, amount_usd = PaymentValidator.validate_payment_amounts(amount_uzs, amount_usd)
        PaymentValidator.validate_currency_match(paid_to_account, amount_uzs, amount_usd)
        PaymentValidator.validate_related_sale(agent, related_sale, amount_uzs, amount_usd, payment_instance)

        return amount_uzs, amount_usd 