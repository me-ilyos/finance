from django.db import transaction
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from .models import Sale
from .forms import SaleForm
from apps.contacts.models import AgentPayment


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
        
        with transaction.atomic():
            # Restore inventory quantity
            acquisition = sale.related_acquisition
            acquisition.available_quantity += sale.quantity
            acquisition.save(update_fields=['available_quantity', 'updated_at'])
            
            # Handle agent debt reversal (no initial payment to remove)
            if sale.agent:
                sale.agent.reduce_debt(sale.total_sale_amount, sale.sale_currency)
            
            # Handle client payment reversal
            elif sale.paid_to_account:
                account = sale.paid_to_account
                account.current_balance -= sale.total_sale_amount
                account.save(update_fields=['current_balance', 'updated_at'])
            
            # Delete the sale
            sale.delete()
            
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