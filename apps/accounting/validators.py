from decimal import Decimal
from django.core.exceptions import ValidationError
from apps.core.constants import CurrencyChoices


class ExpenditureValidator:
    """Centralized validation for expenditures"""

    @staticmethod
    def validate_amount(amount):
        """Validate expenditure amount"""
        if amount is None:
            raise ValidationError("Amount is required.")
        
        if amount <= 0:
            raise ValidationError("Expenditure amount must be positive.")
        
        return amount

    @staticmethod
    def validate_currency_match(paid_from_account, currency):
        """Validate that expenditure currency matches account currency"""
        if not paid_from_account:
            raise ValidationError("Payment account is required.")
        
        if currency not in [choice[0] for choice in CurrencyChoices.choices]:
            raise ValidationError(f"Invalid currency: {currency}")
        
        if paid_from_account.currency != currency:
            raise ValidationError(
                f"Currency mismatch: account uses {paid_from_account.currency}, "
                f"expenditure uses {currency}."
            )

    @staticmethod
    def validate_sufficient_balance(paid_from_account, amount, expenditure_instance=None):
        """Validate that account has sufficient balance"""
        if not paid_from_account or not amount:
            return
        
        available_balance = paid_from_account.current_balance
        
        # For updates, add back the original amount to available balance
        if expenditure_instance and expenditure_instance.pk:
            try:
                from .models import Expenditure
                original = Expenditure.objects.get(pk=expenditure_instance.pk)
                if original.paid_from_account_id == paid_from_account.id:
                    available_balance += original.amount
            except Expenditure.DoesNotExist:
                pass
        
        if available_balance < amount:
            raise ValidationError(
                f"Insufficient balance. Available: {available_balance:,.2f} {paid_from_account.currency}"
            )

    @staticmethod
    def validate_expenditure(expenditure_date, description, amount, currency, paid_from_account, expenditure_instance=None):
        """Main validation method for expenditures"""
        if not description or not description.strip():
            raise ValidationError("Description is required.")
        
        # Validate amount
        amount = ExpenditureValidator.validate_amount(amount)
        
        # Validate currency match
        ExpenditureValidator.validate_currency_match(paid_from_account, currency)
        
        # Validate sufficient balance
        ExpenditureValidator.validate_sufficient_balance(paid_from_account, amount, expenditure_instance)
        
        return {
            'expenditure_date': expenditure_date,
            'description': description.strip(),
            'amount': amount,
            'currency': currency,
            'paid_from_account': paid_from_account
        }


class FinancialAccountValidator:
    """Centralized validation for financial accounts"""

    @staticmethod
    def validate_account_creation(name, account_type, currency, current_balance=None):
        """Validate financial account creation data"""
        if not name or not name.strip():
            raise ValidationError("Account name is required.")
        
        if currency not in [choice[0] for choice in CurrencyChoices.choices]:
            raise ValidationError(f"Invalid currency: {currency}")
        
        if current_balance is not None and current_balance < 0:
            raise ValidationError("Initial balance cannot be negative.")
        
        return {
            'name': name.strip(),
            'account_type': account_type,
            'currency': currency,
            'current_balance': current_balance or Decimal('0.00')
        } 