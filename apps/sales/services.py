import logging
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.apps import apps
from apps.accounting.models import FinancialAccount

logger = logging.getLogger(__name__)


class SaleCalculationService:
    """Service for sale-related calculations"""
    
    @staticmethod
    def calculate_total_sale_amount(quantity, unit_sale_price):
        """Calculate total sale amount"""
        if not quantity or not unit_sale_price:
            return Decimal('0.00')
        return quantity * unit_sale_price
    
    @staticmethod
    def calculate_profit(sale_instance):
        """Calculate profit from sale"""
        if not sale_instance.related_acquisition:
            return Decimal('0.00')
            
        unit_cost = Decimal('0.00')
        acquisition = sale_instance.related_acquisition
        
        if acquisition.transaction_currency == 'UZS':
            unit_cost = acquisition.unit_price_uzs or Decimal('0.00')
        elif acquisition.transaction_currency == 'USD':
            unit_cost = acquisition.unit_price_usd or Decimal('0.00')
        
        total_cost = sale_instance.quantity * unit_cost
        return sale_instance.total_sale_amount - total_cost
    
    @staticmethod
    def determine_sale_currency(related_acquisition):
        """Determine sale currency from acquisition"""
        if not related_acquisition:
            raise ValidationError("Related acquisition is required to determine sale currency")
        return related_acquisition.transaction_currency


class StockManagementService:
    """Service for managing inventory stock during sales"""
    
    @staticmethod
    def validate_stock_availability(acquisition, quantity, current_sale_id=None):
        """Validate that enough stock is available"""
        effective_available_qty = acquisition.available_quantity
        
        # For updates, add back the original quantity
        if current_sale_id:
            try:
                from .models import Sale
                original_sale = Sale.objects.get(pk=current_sale_id)
                if original_sale.related_acquisition_id == acquisition.id:
                    effective_available_qty += original_sale.quantity
            except Sale.DoesNotExist:
                pass
        
        if quantity > effective_available_qty:
            raise ValidationError(
                f"Cannot sell {quantity}. Only {effective_available_qty} available."
            )
        
        return effective_available_qty
    
    @staticmethod
    def update_stock_for_sale(acquisition_id, quantity_change):
        """Update stock when sale is created/updated"""
        from apps.inventory.models import Acquisition
        
        try:
            with transaction.atomic():
                acquisition = Acquisition.objects.select_for_update().get(pk=acquisition_id)
                
                if acquisition.available_quantity < quantity_change:
                    raise ValidationError(
                        f"Insufficient stock. Available: {acquisition.available_quantity}, Required: {quantity_change}"
                    )
                
                acquisition.available_quantity -= quantity_change
                acquisition.save(update_fields=['available_quantity', 'updated_at'])
                
                logger.info(f"Updated stock for acquisition {acquisition_id}: -{quantity_change}")
                return acquisition
                
        except Exception as e:
            logger.error(f"Error updating stock for acquisition {acquisition_id}: {e}")
            raise
    
    @staticmethod
    def revert_stock_for_sale(acquisition_id, quantity_to_revert):
        """Revert stock when sale is deleted/updated"""
        from apps.inventory.models import Acquisition
        
        try:
            with transaction.atomic():
                acquisition = Acquisition.objects.select_for_update().get(pk=acquisition_id)
                acquisition.available_quantity += quantity_to_revert
                acquisition.save(update_fields=['available_quantity', 'updated_at'])
                
                logger.info(f"Reverted stock for acquisition {acquisition_id}: +{quantity_to_revert}")
                return acquisition
                
        except Exception as e:
            logger.error(f"Error reverting stock for acquisition {acquisition_id}: {e}")
            raise


class AgentDebtService:
    """Service for managing agent debt"""
    
    @staticmethod
    def update_agent_debt(agent, amount, currency, operation='add'):
        """Update agent's outstanding balance"""
        if not agent:
            return
            
        try:
            with transaction.atomic():
                agent = agent.__class__.objects.select_for_update().get(pk=agent.pk)
                
                if currency == 'UZS':
                    if operation == 'add':
                        agent.outstanding_balance_uzs += amount
                    else:  # subtract
                        agent.outstanding_balance_uzs -= amount
                elif currency == 'USD':
                    if operation == 'add':
                        agent.outstanding_balance_usd += amount
                    else:  # subtract
                        agent.outstanding_balance_usd -= amount
                
                agent.save(update_fields=['outstanding_balance_uzs', 'outstanding_balance_usd', 'updated_at'])
                
        except Exception as e:
            logger.error(f"Error updating agent debt: {e}")
            raise
    
    @staticmethod
    def create_initial_payment(sale_instance):
        """Create automatic agent payment for initial payment if provided"""
        if not sale_instance.agent or not sale_instance.initial_payment_amount or not sale_instance.paid_to_account:
            return None
            
        AgentPaymentModel = apps.get_model('contacts', 'AgentPayment')
        
        try:
            with transaction.atomic():
                payment_data = {
                    'agent': sale_instance.agent,
                    'payment_date': sale_instance.sale_date,
                    'paid_to_account': sale_instance.paid_to_account,
                    'notes': f"Avtomatik boshlang'ich to'lov (Sotuv ID: {sale_instance.id})",
                    'is_auto_created': True,
                }
                
                # Set amount based on currency
                if sale_instance.sale_currency == 'UZS':
                    payment_data['amount_paid_uzs'] = sale_instance.initial_payment_amount
                    payment_data['amount_paid_usd'] = Decimal('0.00')
                else:
                    payment_data['amount_paid_usd'] = sale_instance.initial_payment_amount
                    payment_data['amount_paid_uzs'] = Decimal('0.00')
                
                # Create the payment (this will automatically update agent balance via payment service)
                payment = AgentPaymentModel.objects.create(**payment_data)
                
                logger.info(f"Created initial payment {payment.id} for sale {sale_instance.id}")
                return payment
                
        except Exception as e:
            logger.error(f"Error creating initial payment: {e}")
            raise


class PaymentService:
    """Service for handling payment processing"""
    
    @staticmethod
    def process_client_payment(sale_instance, is_new_sale=True, original_payment_data=None):
        """Process direct client payment to financial account"""
        if sale_instance.agent or not sale_instance.paid_to_account:
            return
            
        try:
            with transaction.atomic():
                account = FinancialAccount.objects.select_for_update().get(
                    pk=sale_instance.paid_to_account_id
                )
                
                if is_new_sale:
                    account.current_balance += sale_instance.total_sale_amount
                else:
                    # Handle updates
                    if original_payment_data:
                        old_account_id = original_payment_data.get('paid_to_account_id')
                        old_amount = original_payment_data.get('total_sale_amount', Decimal('0.00'))
                        
                        # Revert old payment if account or amount changed
                        if old_account_id and old_account_id != sale_instance.paid_to_account_id:
                            try:
                                old_account = FinancialAccount.objects.select_for_update().get(pk=old_account_id)
                                old_account.current_balance -= old_amount
                                old_account.save(update_fields=['current_balance', 'updated_at'])
                            except FinancialAccount.DoesNotExist:
                                pass
                        elif old_account_id == sale_instance.paid_to_account_id:
                            account.current_balance -= old_amount
                    
                    account.current_balance += sale_instance.total_sale_amount
                
                account.save(update_fields=['current_balance', 'updated_at'])
                logger.info(f"Processed client payment: {sale_instance.total_sale_amount} to account {account.id}")
                
        except Exception as e:
            logger.error(f"Error processing client payment: {e}")
            raise


class SaleService:
    """Main service for sale operations"""
    
    @staticmethod
    def create_sale(sale_data):
        """Create a new sale with all related operations"""
        from .models import Sale
        
        try:
            with transaction.atomic():
                # Validate stock before creating
                StockManagementService.validate_stock_availability(
                    sale_data['related_acquisition'], 
                    sale_data['quantity']
                )
                
                # Create sale instance
                sale = Sale(**sale_data)
                
                # Calculate derived fields
                sale.sale_currency = SaleCalculationService.determine_sale_currency(
                    sale.related_acquisition
                )
                sale.total_sale_amount = SaleCalculationService.calculate_total_sale_amount(
                    sale.quantity, sale.unit_sale_price
                )
                sale.profit = SaleCalculationService.calculate_profit(sale)
                
                # Save the sale
                sale.save()
                
                # Update stock
                StockManagementService.update_stock_for_sale(
                    sale.related_acquisition_id, sale.quantity
                )
                
                # Handle agent operations
                if sale.agent:
                    # Add debt to agent balance
                    print(f"[DEBUG] Before adding sale debt - Agent {sale.agent.id} balance: UZS {sale.agent.outstanding_balance_uzs}, USD {sale.agent.outstanding_balance_usd}")
                    print(f"[DEBUG] Adding sale amount: {sale.total_sale_amount} {sale.sale_currency}")
                        
                    AgentDebtService.update_agent_debt(
                        sale.agent, sale.total_sale_amount, sale.sale_currency, 'add'
                    )
                    
                    # Refresh agent to see updated balance
                    sale.agent.refresh_from_db()
                    print(f"[DEBUG] After adding sale debt - Agent {sale.agent.id} balance: UZS {sale.agent.outstanding_balance_uzs}, USD {sale.agent.outstanding_balance_usd}")
                    
                    # Create initial payment if provided
                    if sale.initial_payment_amount and sale.initial_payment_amount > 0:
                        print(f"[DEBUG] Creating initial payment: {sale.initial_payment_amount} {sale.sale_currency}")
                        initial_payment = AgentDebtService.create_initial_payment(sale)
                        
                        # Refresh agent to see updated balance after payment
                        sale.agent.refresh_from_db()
                        print(f"[DEBUG] After initial payment - Agent {sale.agent.id} balance: UZS {sale.agent.outstanding_balance_uzs}, USD {sale.agent.outstanding_balance_usd}")
                        print(f"[DEBUG] Initial payment created: {initial_payment.id if initial_payment else 'None'}")
                
                # Handle client payment
                if not sale.agent:
                    PaymentService.process_client_payment(sale, is_new_sale=True)
                
                logger.info(f"Created sale {sale.id} successfully")
                return sale
                
        except Exception as e:
            logger.error(f"Error creating sale: {e}")
            raise
    
    @staticmethod
    def update_sale(sale_instance, original_data):
        """Update sale with proper handling of related operations"""
        try:
            with transaction.atomic():
                # Validate stock for update
                StockManagementService.validate_stock_availability(
                    sale_instance.related_acquisition,
                    sale_instance.quantity,
                    sale_instance.pk
                )
                
                # Update calculated fields
                sale_instance.sale_currency = SaleCalculationService.determine_sale_currency(
                    sale_instance.related_acquisition
                )
                sale_instance.total_sale_amount = SaleCalculationService.calculate_total_sale_amount(
                    sale_instance.quantity, sale_instance.unit_sale_price
                )
                sale_instance.profit = SaleCalculationService.calculate_profit(sale_instance)
                
                # Handle stock changes
                original_quantity = original_data.get('quantity', 0)
                original_acquisition_id = original_data.get('related_acquisition_id')
                
                if original_acquisition_id != sale_instance.related_acquisition_id:
                    # Acquisition changed - revert old stock and update new
                    StockManagementService.revert_stock_for_sale(original_acquisition_id, original_quantity)
                    StockManagementService.update_stock_for_sale(sale_instance.related_acquisition_id, sale_instance.quantity)
                else:
                    # Same acquisition - handle quantity difference
                    quantity_diff = sale_instance.quantity - original_quantity
                    if quantity_diff != 0:
                        if quantity_diff > 0:
                            StockManagementService.update_stock_for_sale(sale_instance.related_acquisition_id, quantity_diff)
                        else:
                            StockManagementService.revert_stock_for_sale(sale_instance.related_acquisition_id, abs(quantity_diff))
                
                # Save the updated sale
                sale_instance.save()
                
                # Handle agent debt changes
                original_agent_id = original_data.get('agent_id')
                original_total_amount = original_data.get('total_sale_amount', Decimal('0.00'))
                original_currency = original_data.get('sale_currency')
                
                if sale_instance.agent:
                    if original_agent_id == sale_instance.agent_id:
                        # Same agent - adjust debt difference
                        debt_diff = sale_instance.total_sale_amount - original_total_amount
                        if debt_diff != 0:
                            operation = 'add' if debt_diff > 0 else 'subtract'
                            AgentDebtService.update_agent_debt(
                                sale_instance.agent, abs(debt_diff), sale_instance.sale_currency, operation
                            )
                    else:
                        # Agent changed - revert old and add new
                        if original_agent_id:
                            from apps.contacts.models import Agent
                            try:
                                old_agent = Agent.objects.get(pk=original_agent_id)
                                AgentDebtService.update_agent_debt(
                                    old_agent, original_total_amount, original_currency, 'subtract'
                                )
                            except Agent.DoesNotExist:
                                pass
                        
                        AgentDebtService.update_agent_debt(
                            sale_instance.agent, sale_instance.total_sale_amount, sale_instance.sale_currency, 'add'
                        )
                
                # Handle payment changes
                if not sale_instance.agent:
                    PaymentService.process_client_payment(sale_instance, is_new_sale=False, original_payment_data=original_data)
                
                logger.info(f"Updated sale {sale_instance.id} successfully")
                return sale_instance
                
        except Exception as e:
            logger.error(f"Error updating sale {sale_instance.id}: {e}")
            raise
    
    @staticmethod
    def delete_sale(sale_instance):
        """Delete sale and revert all related operations"""
        try:
            with transaction.atomic():
                # Revert stock
                StockManagementService.revert_stock_for_sale(
                    sale_instance.related_acquisition_id, sale_instance.quantity
                )
                
                # Revert agent debt
                if sale_instance.agent:
                    AgentDebtService.update_agent_debt(
                        sale_instance.agent, sale_instance.total_sale_amount, 
                        sale_instance.sale_currency, 'subtract'
                    )
                
                # Revert client payment
                if not sale_instance.agent and sale_instance.paid_to_account:
                    try:
                        account = FinancialAccount.objects.select_for_update().get(
                            pk=sale_instance.paid_to_account_id
                        )
                        account.current_balance -= sale_instance.total_sale_amount
                        account.save(update_fields=['current_balance', 'updated_at'])
                    except FinancialAccount.DoesNotExist:
                        pass
                
                logger.info(f"Deleted sale {sale_instance.id} successfully")
                
        except Exception as e:
            logger.error(f"Error deleting sale {sale_instance.id}: {e}")
            raise 