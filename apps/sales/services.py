from django.db import transaction
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from .models import Sale, TicketReturn
from .forms import SaleForm
from apps.contacts.models import AgentPayment
import logging

logger = logging.getLogger(__name__)


class SaleService:
    """Service class to handle sale business logic"""
    
    @staticmethod
    def create_sale(form):
        """Create sale with complete business logic"""
        with transaction.atomic():
            # Create sale instance
            sale = form.save(commit=False)
            
            # Set calculated fields
            sale.sale_currency = sale.related_acquisition.currency
            sale.total_sale_amount = sale.quantity * sale.unit_sale_price
            
            # Calculate profit
            unit_cost = sale.related_acquisition.unit_price
            total_cost = sale.quantity * unit_cost
            sale.profit = sale.total_sale_amount - total_cost
            
            # Add salesperson
            if 'salesperson' in form.cleaned_data:
                sale.salesperson = form.cleaned_data['salesperson']
            
            sale.save()
            
            # Update stock
            acquisition = sale.related_acquisition
            acquisition.available_quantity -= sale.quantity
            acquisition.save(update_fields=['available_quantity', 'updated_at'])
            
            # Handle agent debt (no initial payment)
            if sale.agent:
                sale.agent.add_debt(sale.total_sale_amount, sale.sale_currency)
            
            # Handle client payment (customers pay immediately)
            elif sale.paid_to_account:
                account = sale.paid_to_account
                account.current_balance += sale.total_sale_amount
                account.save(update_fields=['current_balance', 'updated_at'])
            
            return sale

    @staticmethod
    def delete_sale(sale_id, user):
        """Delete sale with complete transaction rollback"""
        if not user.is_superuser:
            raise ValidationError("Faqat administratorlar sotuvni o'chira oladi.")
        
        sale = get_object_or_404(Sale, pk=sale_id)
        logger.info(f"Starting deletion of sale {sale_id}")
        logger.info(f"Sale details: Agent={sale.agent}, Amount={sale.total_sale_amount}, Currency={sale.sale_currency}")
        
        with transaction.atomic():
            # Restore inventory quantity
            acquisition = sale.related_acquisition
            acquisition.available_quantity += sale.quantity
            acquisition.save(update_fields=['available_quantity', 'updated_at'])
            logger.info(f"Restored {sale.quantity} units to acquisition {acquisition.id}")
            
            # Handle agent debt reversal (no initial payment to remove)
            if sale.agent:
                logger.info(f"Agent {sale.agent.id} ({sale.agent.name}) balance before debt reduction:")
                logger.info(f"  UZS: {sale.agent.balance_uzs}")
                logger.info(f"  USD: {sale.agent.balance_usd}")
                logger.info(f"Reducing debt by {sale.total_sale_amount} {sale.sale_currency}")
                
                sale.agent.reduce_debt(sale.total_sale_amount, sale.sale_currency)
                
                # Refresh from database to get updated values
                sale.agent.refresh_from_db()
                logger.info(f"Agent {sale.agent.id} balance after debt reduction:")
                logger.info(f"  UZS: {sale.agent.balance_uzs}")
                logger.info(f"  USD: {sale.agent.balance_usd}")
            
            # Handle client payment reversal
            elif sale.paid_to_account:
                logger.info(f"Reversing client payment from account {sale.paid_to_account.name}")
                account = sale.paid_to_account
                account.current_balance -= sale.total_sale_amount
                account.save(update_fields=['current_balance', 'updated_at'])
            
            # Delete the sale
            logger.info(f"Deleting sale {sale_id} from database")
            sale.delete()
            logger.info(f"Sale {sale_id} successfully deleted")
            
            return True

    @staticmethod
    def update_sale(original_sale, form):
        """Update sale with complete business logic handling"""
        with transaction.atomic():
            # Store original values
            original_quantity = original_sale.quantity
            original_agent = original_sale.agent
            original_total_amount = original_sale.total_sale_amount
            original_paid_account = original_sale.paid_to_account
            original_acquisition = original_sale.related_acquisition
            original_currency = original_sale.sale_currency
            
            # Get new values
            new_sale = form.save(commit=False)
            new_quantity = new_sale.quantity
            new_agent = new_sale.agent
            new_acquisition = new_sale.related_acquisition
            new_unit_price = new_sale.unit_sale_price
            new_paid_account = new_sale.paid_to_account
            
            # Calculate new totals
            new_sale.sale_currency = new_acquisition.currency
            new_sale.total_sale_amount = new_quantity * new_unit_price
            new_unit_cost = new_acquisition.unit_price
            new_total_cost = new_quantity * new_unit_cost
            new_sale.profit = new_sale.total_sale_amount - new_total_cost
            
            # Handle inventory changes
            if original_acquisition.id != new_acquisition.id or original_quantity != new_quantity:
                # Restore original inventory
                original_acquisition.available_quantity += original_quantity
                original_acquisition.save(update_fields=['available_quantity', 'updated_at'])
                
                # Update new inventory
                new_acquisition.available_quantity -= new_quantity
                new_acquisition.save(update_fields=['available_quantity', 'updated_at'])
            
            # Handle agent/client changes
            if original_agent != new_agent:
                SaleService._handle_buyer_change(
                    original_sale, original_agent, original_total_amount, 
                    original_currency, original_paid_account,
                    new_sale, new_agent, new_paid_account
                )
            # Handle amount changes for same buyer type
            else:
                SaleService._handle_amount_changes(
                    original_sale, original_agent, original_total_amount, 
                    original_currency, original_paid_account,
                    new_sale, new_paid_account
                )
            
            # Save the updated sale
            new_sale.save()
            
            return new_sale

    @staticmethod
    def _handle_buyer_change(original_sale, original_agent, original_total_amount, 
                           original_currency, original_paid_account,
                           new_sale, new_agent, new_paid_account):
        """Handle buyer type changes (agent to client or vice versa)"""
        # Remove original agent debt (no initial payment to remove)
        if original_agent:
            original_agent.reduce_debt(original_total_amount, original_currency)
        
        # Remove original client payment
        elif original_paid_account:
            original_paid_account.current_balance -= original_total_amount
            original_paid_account.save(update_fields=['current_balance', 'updated_at'])
        
        # Add new agent debt (no initial payment)
        if new_agent:
            new_agent.add_debt(new_sale.total_sale_amount, new_sale.sale_currency)
        
        # Add new client payment (customers pay immediately)
        elif new_paid_account:
            new_paid_account.current_balance += new_sale.total_sale_amount
            new_paid_account.save(update_fields=['current_balance', 'updated_at'])

    @staticmethod
    def _handle_amount_changes(original_sale, original_agent, original_total_amount, 
                             original_currency, original_paid_account,
                             new_sale, new_paid_account):
        """Handle amount changes for same buyer type"""
        if original_agent:  # Agent sale (no initial payment)
            # Adjust agent debt only
            debt_diff = new_sale.total_sale_amount - original_total_amount
            if debt_diff != 0:
                original_agent.add_debt(debt_diff, new_sale.sale_currency)
        
        elif original_paid_account:  # Client sale (immediate payment)
            # Adjust account balance
            amount_diff = new_sale.total_sale_amount - original_total_amount
            if amount_diff != 0:
                original_paid_account.current_balance += amount_diff
                original_paid_account.save(update_fields=['current_balance', 'updated_at']) 


class TicketReturnService:
    """Service class to handle ticket return business logic"""
    
    @staticmethod
    def create_return(form, user):
        """Create ticket return with complete business logic"""
        with transaction.atomic():
            return_instance = form.save(commit=False)
            
            # Set currencies from original sale
            return_instance.fine_currency = return_instance.original_sale.sale_currency
            return_instance.supplier_fine_currency = return_instance.original_sale.sale_currency
            
            return_instance.save()
            
            # Restore inventory
            acquisition = return_instance.original_sale.related_acquisition
            acquisition.available_quantity += return_instance.quantity_returned
            acquisition.save(update_fields=['available_quantity', 'updated_at'])
            
            # Handle return based on sale type
            if return_instance.is_customer_return:
                TicketReturnService._handle_customer_return(return_instance)
            else:
                TicketReturnService._handle_agent_return(return_instance)
            
            return return_instance
    
    @staticmethod
    def _handle_customer_return(return_instance):
        """Handle customer return business logic"""
        sale = return_instance.original_sale
        
        # 1. Refund customer the original purchase price (what we paid supplier), not the sale price
        if sale.paid_to_account:
            refund_amount = return_instance.returned_acquisition_amount  # Original purchase price from supplier
            account = sale.paid_to_account
            account.current_balance -= refund_amount
            account.save(update_fields=['current_balance', 'updated_at'])
            logger.info(f"Refunded original purchase price {refund_amount} {sale.related_acquisition.currency} to customer account {account.name}")
        
        # 2. Collect fine from customer (subtract from the account where they paid)
        if sale.paid_to_account and return_instance.total_fine_amount > 0:
            fine_amount = return_instance.total_fine_amount
            account = sale.paid_to_account
            account.current_balance -= fine_amount  # Take fine from customer
            account.save(update_fields=['current_balance', 'updated_at'])
            logger.info(f"Collected fine {fine_amount} {return_instance.fine_currency} from customer account {account.name}")
        
        # 3. If fine is paid to a different account, add it there
        if return_instance.fine_paid_to_account and return_instance.fine_paid_to_account != sale.paid_to_account:
            fine_amount = return_instance.total_fine_amount
            account = return_instance.fine_paid_to_account
            account.current_balance += fine_amount
            account.save(update_fields=['current_balance', 'updated_at'])
            logger.info(f"Added fine {fine_amount} {return_instance.fine_currency} to account {account.name}")
        
        # 4. Reduce supplier debt for returned tickets (based on what we originally paid them)
        # AND add supplier fine to supplier debt
        supplier = sale.related_acquisition.supplier
        returned_acquisition_amount = return_instance.returned_acquisition_amount
        supplier_fine_amount = return_instance.total_supplier_fine_amount
        
        # Reduce debt for returned tickets (what we originally paid them)
        supplier.reduce_debt(returned_acquisition_amount, sale.related_acquisition.currency)
        logger.info(f"Reduced supplier {supplier.name} debt by {returned_acquisition_amount} {sale.related_acquisition.currency} for returned tickets")
        
        # Add supplier fine
        supplier.add_debt(supplier_fine_amount, return_instance.supplier_fine_currency)
        logger.info(f"Added supplier fine {supplier_fine_amount} {return_instance.supplier_fine_currency} to supplier {supplier.name}")
    
    @staticmethod
    def _handle_agent_return(return_instance):
        """Handle agent return business logic"""
        sale = return_instance.original_sale
        agent = sale.agent
        
        # 1. Reduce agent debt for returned tickets (based on original purchase price, not sale price)
        returned_amount = return_instance.returned_acquisition_amount
        agent.reduce_debt(returned_amount, sale.related_acquisition.currency)
        logger.info(f"Reduced agent {agent.name} debt by {returned_amount} {sale.related_acquisition.currency} (original purchase price)")
        
        # 2. Add fine to agent debt
        fine_amount = return_instance.total_fine_amount
        agent.add_debt(fine_amount, return_instance.fine_currency)
        logger.info(f"Added fine {fine_amount} {return_instance.fine_currency} to agent {agent.name} debt")
        
        # 3. Reduce supplier debt for returned tickets (based on what we originally paid them)
        # AND add supplier fine to supplier debt
        supplier = sale.related_acquisition.supplier
        returned_acquisition_amount = return_instance.returned_acquisition_amount
        supplier_fine_amount = return_instance.total_supplier_fine_amount
        
        # Reduce debt for returned tickets (what we originally paid them)
        supplier.reduce_debt(returned_acquisition_amount, sale.related_acquisition.currency)
        logger.info(f"Reduced supplier {supplier.name} debt by {returned_acquisition_amount} {sale.related_acquisition.currency} for returned tickets")
        
        # Add supplier fine
        supplier.add_debt(supplier_fine_amount, return_instance.supplier_fine_currency)
        logger.info(f"Added supplier fine {supplier_fine_amount} {return_instance.supplier_fine_currency} to supplier {supplier.name}")
    
    @staticmethod
    def delete_return(return_id, user):
        """Delete return with complete transaction rollback"""
        if not user.is_superuser:
            raise ValidationError("Faqat administratorlar qaytarishni o'chira oladi.")
        
        return_instance = get_object_or_404(TicketReturn, pk=return_id)
        logger.info(f"Starting deletion of return {return_id}")
        
        with transaction.atomic():
            # Reverse inventory restoration
            acquisition = return_instance.original_sale.related_acquisition
            acquisition.available_quantity -= return_instance.quantity_returned
            acquisition.save(update_fields=['available_quantity', 'updated_at'])
            logger.info(f"Reversed inventory restoration for {return_instance.quantity_returned} units")
            
            # Reverse business logic based on return type
            if return_instance.is_customer_return:
                TicketReturnService._reverse_customer_return(return_instance)
            else:
                TicketReturnService._reverse_agent_return(return_instance)
            
            # Delete the return
            logger.info(f"Deleting return {return_id} from database")
            return_instance.delete()
            logger.info(f"Return {return_id} successfully deleted")
            
            return True
    
    @staticmethod
    def _reverse_customer_return(return_instance):
        """Reverse customer return business logic"""
        sale = return_instance.original_sale
        
        # 1. Reverse customer refund (give back the original purchase price we refunded)
        if sale.paid_to_account:
            refund_amount = return_instance.returned_acquisition_amount  # Original purchase price from supplier
            account = sale.paid_to_account
            account.current_balance += refund_amount
            account.save(update_fields=['current_balance', 'updated_at'])
            logger.info(f"Reversed customer refund {refund_amount} {sale.related_acquisition.currency}")
        
        # 2. Reverse fine collection (give back the fine we collected)
        if sale.paid_to_account and return_instance.total_fine_amount > 0:
            fine_amount = return_instance.total_fine_amount
            account = sale.paid_to_account
            account.current_balance += fine_amount  # Give back fine to customer
            account.save(update_fields=['current_balance', 'updated_at'])
            logger.info(f"Reversed fine collection {fine_amount} {return_instance.fine_currency}")
        
        # 3. Reverse fine payment to different account
        if return_instance.fine_paid_to_account and return_instance.fine_paid_to_account != sale.paid_to_account:
            fine_amount = return_instance.total_fine_amount
            account = return_instance.fine_paid_to_account
            account.current_balance -= fine_amount
            account.save(update_fields=['current_balance', 'updated_at'])
            logger.info(f"Reversed fine payment {fine_amount} {return_instance.fine_currency}")
        
        # 4. Reverse supplier debt reduction and supplier fine
        supplier = sale.related_acquisition.supplier
        returned_acquisition_amount = return_instance.returned_acquisition_amount
        supplier_fine_amount = return_instance.total_supplier_fine_amount
        
        # Reverse debt reduction for returned tickets
        supplier.add_debt(returned_acquisition_amount, sale.related_acquisition.currency)
        logger.info(f"Reversed supplier debt reduction {returned_acquisition_amount} {sale.related_acquisition.currency}")
        
        # Reverse supplier fine
        supplier.reduce_debt(supplier_fine_amount, return_instance.supplier_fine_currency)
        logger.info(f"Reversed supplier fine {supplier_fine_amount} {return_instance.supplier_fine_currency}")
    
    @staticmethod
    def _reverse_agent_return(return_instance):
        """Reverse agent return business logic"""
        sale = return_instance.original_sale
        agent = sale.agent
        
        # 1. Reverse agent debt reduction (add back original purchase price)
        returned_amount = return_instance.returned_acquisition_amount
        agent.add_debt(returned_amount, sale.related_acquisition.currency)
        logger.info(f"Reversed agent debt reduction {returned_amount} {sale.related_acquisition.currency} (original purchase price)")
        
        # 2. Reverse fine addition
        fine_amount = return_instance.total_fine_amount
        agent.reduce_debt(fine_amount, return_instance.fine_currency)
        logger.info(f"Reversed fine addition {fine_amount} {return_instance.fine_currency}")
        
        # 3. Reverse supplier debt reduction and supplier fine
        supplier = sale.related_acquisition.supplier
        returned_acquisition_amount = return_instance.returned_acquisition_amount
        supplier_fine_amount = return_instance.total_supplier_fine_amount
        
        # Reverse debt reduction for returned tickets
        supplier.add_debt(returned_acquisition_amount, sale.related_acquisition.currency)
        logger.info(f"Reversed supplier debt reduction {returned_acquisition_amount} {sale.related_acquisition.currency}")
        
        # Reverse supplier fine
        supplier.reduce_debt(supplier_fine_amount, return_instance.supplier_fine_currency)
        logger.info(f"Reversed supplier fine {supplier_fine_amount} {return_instance.supplier_fine_currency}") 