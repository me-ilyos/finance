import logging
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Sum
from apps.core.constants import CurrencyChoices, ValidationMessages

logger = logging.getLogger(__name__)


class AgentPaymentService:
    """Service class to handle agent payment operations"""

    @staticmethod
    def determine_payment_currency(amount_uzs, amount_usd):
        """Determine payment currency based on amounts"""
        if amount_uzs > 0 and amount_usd == 0:
            return CurrencyChoices.UZS
        elif amount_usd > 0 and amount_uzs == 0:
            return CurrencyChoices.USD
        elif amount_uzs > 0 and amount_usd > 0:
            raise ValidationError(ValidationMessages.SINGLE_CURRENCY_ONLY)
        else:
            raise ValidationError(ValidationMessages.PAYMENT_REQUIRED)

    @staticmethod
    def get_payment_amount(payment_currency, amount_uzs, amount_usd):
        """Get the payment amount in the determined currency"""
        if payment_currency == CurrencyChoices.UZS:
            return amount_uzs
        elif payment_currency == CurrencyChoices.USD:
            return amount_usd
        return Decimal('0.00')

    @staticmethod
    def create_payment(form, agent):
        """Create agent payment with proper error handling - Consolidated from views"""
        try:
            with transaction.atomic():
                payment = form.save(commit=False)
                payment.agent = agent
                payment.save()
                
            logger.info(f"Created payment {payment.pk} for agent {agent.pk}")
            return payment, None
            
        except ValidationError as e:
            error_msg = f"To'lovni saqlashda xatolik: {e}"
            logger.error(f"Validation error creating payment for agent {agent.pk}: {e}")
            return None, error_msg
            
        except Exception as e:
            error_msg = f"Kutilmagan xatolik: {e}"
            logger.error(f"Unexpected error creating payment for agent {agent.pk}: {e}")
            return None, error_msg

    @staticmethod
    def update_financial_account(payment, original_payment=None):
        """Update financial account balance for payment"""
        from apps.accounting.models import FinancialAccount
        
        try:
            payment_currency = AgentPaymentService.determine_payment_currency(
                payment.amount_paid_uzs, payment.amount_paid_usd
            )
            payment_amount = AgentPaymentService.get_payment_amount(
                payment_currency, payment.amount_paid_uzs, payment.amount_paid_usd
            )

            account = payment.paid_to_account
            
            if original_payment:
                # Handle update case
                original_currency = AgentPaymentService.determine_payment_currency(
                    original_payment.amount_paid_uzs, original_payment.amount_paid_usd
                )
                original_amount = AgentPaymentService.get_payment_amount(
                    original_currency, original_payment.amount_paid_uzs, original_payment.amount_paid_usd
                )
                
                if original_payment.paid_to_account_id == account.id:
                    # Same account, adjust difference
                    account.current_balance += (payment_amount - original_amount)
                else:
                    # Account changed, revert from old and add to new
                    old_account = FinancialAccount.objects.get(pk=original_payment.paid_to_account_id)
                    old_account.current_balance -= original_amount
                    old_account.save(update_fields=['current_balance', 'updated_at'])
                    account.current_balance += payment_amount
            else:
                # New payment
                account.current_balance += payment_amount
            
            account.save(update_fields=['current_balance', 'updated_at'])
            logger.info(f"Updated financial account {account.id} balance by {payment_amount}")
            
        except Exception as e:
            logger.error(f"Error updating financial account for payment {payment.id}: {e}")
            raise

    @staticmethod
    def update_agent_balance(payment, original_payment=None):
        """Update agent's outstanding balance"""
        try:
            agent = payment.agent
            amount_uzs_diff = payment.amount_paid_uzs
            amount_usd_diff = payment.amount_paid_usd

            if original_payment:
                # Calculate difference for updates
                amount_uzs_diff = payment.amount_paid_uzs - original_payment.amount_paid_uzs
                amount_usd_diff = payment.amount_paid_usd - original_payment.amount_paid_usd

            agent.outstanding_balance_uzs -= amount_uzs_diff
            agent.outstanding_balance_usd -= amount_usd_diff
            agent.save(update_fields=['outstanding_balance_uzs', 'outstanding_balance_usd', 'updated_at'])
            
            logger.info(f"Updated agent {agent.id} balance: UZS -{amount_uzs_diff}, USD -{amount_usd_diff}")
            
        except Exception as e:
            logger.error(f"Error updating agent balance for payment {payment.id}: {e}")
            raise

    @staticmethod
    def update_related_sale(payment, original_payment=None):
        """Update related sale's paid amount"""
        if not payment.related_sale:
            return
            
        try:
            from apps.sales.models import Sale
            
            payment_currency = AgentPaymentService.determine_payment_currency(
                payment.amount_paid_uzs, payment.amount_paid_usd
            )
            payment_amount = AgentPaymentService.get_payment_amount(
                payment_currency, payment.amount_paid_uzs, payment.amount_paid_usd
            )

            sale = Sale.objects.get(pk=payment.related_sale.id)
            
            # Handle related sale changes
            if original_payment and original_payment.related_sale_id and original_payment.related_sale_id != payment.related_sale_id:
                # Related sale changed, revert from old sale
                old_sale = Sale.objects.get(pk=original_payment.related_sale_id)
                original_currency = AgentPaymentService.determine_payment_currency(
                    original_payment.amount_paid_uzs, original_payment.amount_paid_usd
                )
                original_amount = AgentPaymentService.get_payment_amount(
                    original_currency, original_payment.amount_paid_uzs, original_payment.amount_paid_usd
                )
                old_sale.paid_amount_on_this_sale -= original_amount
                old_sale.save(update_fields=['paid_amount_on_this_sale', 'updated_at'])

            # Calculate contribution to current sale
            current_contribution = payment_amount if sale.sale_currency == payment_currency else Decimal('0.00')
            previous_contribution = Decimal('0.00')
            
            if original_payment and (not original_payment.related_sale_id or original_payment.related_sale_id == payment.related_sale_id):
                original_currency = AgentPaymentService.determine_payment_currency(
                    original_payment.amount_paid_uzs, original_payment.amount_paid_usd
                )
                if sale.sale_currency == original_currency:
                    previous_contribution = AgentPaymentService.get_payment_amount(
                        original_currency, original_payment.amount_paid_uzs, original_payment.amount_paid_usd
                    )

            # Update sale
            change_amount = current_contribution - previous_contribution
            sale.paid_amount_on_this_sale += change_amount
            sale.paid_amount_on_this_sale = max(Decimal('0.00'), min(sale.paid_amount_on_this_sale, sale.total_sale_amount))
            sale.save(update_fields=['paid_amount_on_this_sale', 'updated_at'])
            
            logger.info(f"Updated sale {sale.id} paid amount by {change_amount}")
            
        except Exception as e:
            logger.error(f"Error updating related sale for payment {payment.id}: {e}")
            raise

    @staticmethod
    def process_payment(payment, original_payment=None):
        """Main method to process agent payment with all updates"""
        with transaction.atomic():
            AgentPaymentService.update_financial_account(payment, original_payment)
            AgentPaymentService.update_agent_balance(payment, original_payment)
            AgentPaymentService.update_related_sale(payment, original_payment)


class AgentService:
    """Service class for agent operations"""

    @staticmethod
    def update_balance_on_sale(agent, sale_amount, sale_currency):
        """Update agent balance when sale is created"""
        try:
            if sale_currency == CurrencyChoices.UZS:
                agent.outstanding_balance_uzs += sale_amount
            elif sale_currency == CurrencyChoices.USD:
                agent.outstanding_balance_usd += sale_amount
            agent.save(update_fields=['outstanding_balance_uzs', 'outstanding_balance_usd', 'updated_at'])
            
            logger.info(f"Updated agent {agent.id} balance for sale: {sale_amount} {sale_currency}")
            
        except Exception as e:
            logger.error(f"Error updating agent balance for sale: {e}")
            raise

    @staticmethod
    def get_agent_totals(agent):
        """Get all calculated totals for an agent - moved from model"""
        from django.apps import apps
        Sale = apps.get_model('sales', 'Sale')
        
        return {
            'total_sales_uzs': Sale.objects.filter(
                agent=agent, sale_currency=CurrencyChoices.UZS
            ).aggregate(total=Sum('total_sale_amount'))['total'] or Decimal('0.00'),
            
            'total_sales_usd': Sale.objects.filter(
                agent=agent, sale_currency=CurrencyChoices.USD
            ).aggregate(total=Sum('total_sale_amount'))['total'] or Decimal('0.00'),
            
            'total_payments_uzs': agent.payments.filter(
                paid_to_account__currency=CurrencyChoices.UZS
            ).aggregate(total=Sum('amount_paid_uzs'))['total'] or Decimal('0.00'),
            
            'total_payments_usd': agent.payments.filter(
                paid_to_account__currency=CurrencyChoices.USD
            ).aggregate(total=Sum('amount_paid_usd'))['total'] or Decimal('0.00'),
        }


class ContactFormService:
    """Service class for contact form operations"""

    @staticmethod
    def create_agent(validated_data):
        """Create a new agent with optional initial balance"""
        from .models import Agent
        try:
            agent = Agent.objects.create(**validated_data)
            
            # Log balance information if provided
            if validated_data.get('outstanding_balance_uzs', 0) != 0 or validated_data.get('outstanding_balance_usd', 0) != 0:
                logger.info(f"Created new agent with initial balance: {agent.name} - "
                           f"UZS: {validated_data.get('outstanding_balance_uzs', 0)}, "
                           f"USD: {validated_data.get('outstanding_balance_usd', 0)}")
            else:
                logger.info(f"Created new agent: {agent.name}")
                
            return agent
        except Exception as e:
            logger.error(f"Error creating agent: {e}")
            raise

    @staticmethod
    def create_supplier(validated_data):
        """Create a new supplier with optional initial balance"""
        from .models import Supplier
        try:
            supplier = Supplier.objects.create(**validated_data)
            
            # Log balance information if provided
            if validated_data.get('current_balance_uzs', 0) != 0 or validated_data.get('current_balance_usd', 0) != 0:
                logger.info(f"Created new supplier with initial balance: {supplier.name} - "
                           f"UZS: {validated_data.get('current_balance_uzs', 0)}, "
                           f"USD: {validated_data.get('current_balance_usd', 0)}")
            else:
                logger.info(f"Created new supplier: {supplier.name}")
                
            return supplier
        except Exception as e:
            logger.error(f"Error creating supplier: {e}")
            raise

    @staticmethod
    def validate_balance_fields(balance_uzs, balance_usd, entity_type="agent"):
        """Validate balance fields for agents or suppliers"""
        errors = {}
        
        if balance_uzs is not None and balance_uzs < -999999999.99:
            errors['balance_uzs'] = f"{entity_type.title()} balans UZS juda katta manfiy qiymat"
            
        if balance_usd is not None and balance_usd < -999999999.99:
            errors['balance_usd'] = f"{entity_type.title()} balans USD juda katta manfiy qiymat"
            
        if balance_uzs is not None and balance_uzs > 999999999.99:
            errors['balance_uzs'] = f"{entity_type.title()} balans UZS juda katta musbat qiymat"
            
        if balance_usd is not None and balance_usd > 999999999.99:
            errors['balance_usd'] = f"{entity_type.title()} balans USD juda katta musbat qiymat"
            
        return errors 