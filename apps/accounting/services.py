import logging
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.core.constants import CurrencyChoices

logger = logging.getLogger(__name__)


class FinancialAccountService:
    """Service class to handle financial account balance operations"""
    
    @staticmethod
    def create_financial_account(form_data):
        """Create a new financial account with proper validation and balance setup"""
        from .models import FinancialAccount
        from .validators import FinancialAccountValidator
        
        try:
            with transaction.atomic():
                # Validate data using validator
                validated_data = FinancialAccountValidator.validate_financial_account(
                    name=form_data.get('name'),
                    account_type=form_data.get('account_type'),
                    currency=form_data.get('currency'),
                    current_balance=form_data.get('current_balance'),
                    account_details=form_data.get('account_details')
                )
                
                # Create the account
                account = FinancialAccount.objects.create(**validated_data)
                
                logger.info(
                    f"Created financial account {account.id}: {account.name} "
                    f"with balance {account.formatted_balance()}"
                )
                return account
                
        except Exception as e:
            logger.error(f"Error creating financial account: {e}")
            raise

    @staticmethod
    def update_financial_account(account, form_data):
        """Update existing financial account"""
        from .validators import FinancialAccountValidator
        
        try:
            with transaction.atomic():
                # Validate data using validator
                validated_data = FinancialAccountValidator.validate_financial_account(
                    name=form_data.get('name'),
                    account_type=form_data.get('account_type'),
                    currency=form_data.get('currency'),
                    current_balance=form_data.get('current_balance'),
                    account_details=form_data.get('account_details'),
                    account_instance=account
                )
                
                # Update account fields
                for field, value in validated_data.items():
                    setattr(account, field, value)
                
                account.save()
                logger.info(f"Updated financial account {account.id}: {account.name}")
                return account
                
        except Exception as e:
            logger.error(f"Error updating financial account {account.id}: {e}")
            raise

    @staticmethod
    def update_balance_for_payment(account_id, amount, operation='add'):
        """Update account balance for payment operations"""
        from .models import FinancialAccount
        
        with transaction.atomic():
            account = FinancialAccount.objects.select_for_update().get(pk=account_id)
            if operation == 'add':
                account.current_balance += amount
            elif operation == 'subtract':
                account.current_balance -= amount
            account.save(update_fields=['current_balance', 'updated_at'])
            logger.info(f"Updated account {account_id} balance by {amount} for payment ({operation})")
            return account
    
    @staticmethod
    def update_balance_for_expenditure(account_id, amount, operation='deduct'):
        """Update account balance for expenditure operations"""
        from .models import FinancialAccount
        
        with transaction.atomic():
            account = FinancialAccount.objects.select_for_update().get(pk=account_id)
            if operation == 'deduct':
                account.current_balance -= amount
            elif operation == 'add_back':
                account.current_balance += amount
            account.save(update_fields=['current_balance', 'updated_at'])
            logger.info(f"Updated account {account_id} balance by {amount} ({operation})")
            return account
    
    @staticmethod
    def handle_expenditure_update(expenditure, original_expenditure):
        """Handle balance updates when expenditure is modified"""
        with transaction.atomic():
            # If account changed, add back to old account
            if original_expenditure.paid_from_account_id != expenditure.paid_from_account_id:
                FinancialAccountService.update_balance_for_expenditure(
                    original_expenditure.paid_from_account_id, 
                    original_expenditure.amount, 
                    'add_back'
                )
                # Deduct from new account
                FinancialAccountService.update_balance_for_expenditure(
                    expenditure.paid_from_account_id, 
                    expenditure.amount, 
                    'deduct'
                )
            else:
                # Same account, handle amount difference
                amount_difference = expenditure.amount - original_expenditure.amount
                if amount_difference != 0:
                    operation = 'deduct' if amount_difference > 0 else 'add_back'
                    FinancialAccountService.update_balance_for_expenditure(
                        expenditure.paid_from_account_id, 
                        abs(amount_difference), 
                        operation
                    )


class ExpenditureService:
    """Service class for expenditure operations"""

    @staticmethod
    def create_expenditure(form_data):
        """Create a new expenditure with proper balance updates"""
        from .models import Expenditure
        
        try:
            with transaction.atomic():
                expenditure = Expenditure.objects.create(**form_data)
                FinancialAccountService.update_balance_for_expenditure(
                    expenditure.paid_from_account_id, 
                    expenditure.amount, 
                    'deduct'
                )
                logger.info(f"Created expenditure {expenditure.id}: {expenditure.description}")
                return expenditure
                
        except Exception as e:
            logger.error(f"Error creating expenditure: {e}")
            raise

    @staticmethod
    def update_expenditure(expenditure, original_expenditure):
        """Update expenditure with proper balance adjustments"""
        try:
            with transaction.atomic():
                expenditure.save()
                FinancialAccountService.handle_expenditure_update(expenditure, original_expenditure)
                logger.info(f"Updated expenditure {expenditure.id}")
                return expenditure
                
        except Exception as e:
            logger.error(f"Error updating expenditure {expenditure.id}: {e}")
            raise

    @staticmethod
    def delete_expenditure(expenditure):
        """Delete expenditure and revert balance changes"""
        try:
            with transaction.atomic():
                # Add back the amount to the account
                FinancialAccountService.update_balance_for_expenditure(
                    expenditure.paid_from_account_id, 
                    expenditure.amount, 
                    'add_back'
                )
                expenditure_id = expenditure.id
                expenditure.delete()
                logger.info(f"Deleted expenditure {expenditure_id}")
                
        except Exception as e:
            logger.error(f"Error deleting expenditure: {e}")
            raise 