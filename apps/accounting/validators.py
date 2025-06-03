from decimal import Decimal
from django.core.exceptions import ValidationError
from apps.core.constants import CurrencyChoices, AccountTypeChoices


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
    def validate_name(name, account_instance=None):
        """Validate account name uniqueness"""
        if not name or not name.strip():
            raise ValidationError("Hisob nomi kiritilishi shart.")
        
        name = name.strip()
        
        # Check for duplicate names (excluding current instance)
        from .models import FinancialAccount
        existing_account = FinancialAccount.objects.filter(name=name)
        if account_instance and account_instance.pk:
            existing_account = existing_account.exclude(pk=account_instance.pk)
        
        if existing_account.exists():
            raise ValidationError("Bu nomli hisob allaqachon mavjud.")
        
        return name

    @staticmethod
    def validate_account_type(account_type):
        """Validate account type"""
        if account_type not in [choice[0] for choice in AccountTypeChoices.choices]:
            raise ValidationError(f"Noto'g'ri hisob turi: {account_type}")
        return account_type

    @staticmethod
    def validate_currency(currency):
        """Validate currency"""
        if currency not in [choice[0] for choice in CurrencyChoices.choices]:
            raise ValidationError(f"Noto'g'ri valyuta: {currency}")
        return currency

    @staticmethod
    def validate_balance(current_balance, account_instance=None):
        """Validate balance"""
        if current_balance is None:
            current_balance = Decimal('0.00')
        
        if current_balance < 0:
            raise ValidationError("Balans manfiy bo'lishi mumkin emas.")
        
        return current_balance

    @staticmethod
    def validate_financial_account(name, account_type, currency, current_balance=None, account_details=None, account_instance=None):
        """Main validation method for financial accounts"""
        
        # Validate all fields
        validated_name = FinancialAccountValidator.validate_name(name, account_instance)
        validated_account_type = FinancialAccountValidator.validate_account_type(account_type)
        validated_currency = FinancialAccountValidator.validate_currency(currency)
        validated_balance = FinancialAccountValidator.validate_balance(current_balance, account_instance)
        
        return {
            'name': validated_name,
            'account_type': validated_account_type,
            'currency': validated_currency,
            'current_balance': validated_balance,
            'account_details': account_details.strip() if account_details else None
        } 