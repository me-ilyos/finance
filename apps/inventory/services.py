from django.db import transaction
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from .models import Acquisition, Ticket
from .forms import AcquisitionForm


class AcquisitionService:
    """Service class to handle acquisition business logic"""
    
    @staticmethod
    def create_acquisition(form):
        """Create acquisition with complete business logic"""
        with transaction.atomic():
            # Create ticket first
            ticket = Ticket.objects.create(
                ticket_type=form.cleaned_data['ticket_type'],
                description=form.cleaned_data['ticket_description'],
                departure_date_time=form.cleaned_data['ticket_departure_date_time'],
                arrival_date_time=form.cleaned_data.get('ticket_arrival_date_time')
            )
            
            # Create acquisition
            acquisition = form.save(commit=False)
            acquisition.ticket = ticket
            
            # Add salesperson if available
            if 'salesperson' in form.cleaned_data:
                acquisition.salesperson = form.cleaned_data['salesperson']
            
            acquisition.save()
            
            # Add debt to supplier
            acquisition.supplier.add_debt(acquisition.total_amount, acquisition.currency)
            
            return acquisition

    @staticmethod
    def delete_acquisition(acquisition_id, user):
        """Soft delete acquisition with complete transaction rollback"""
        print(f"DEBUG: Attempting to soft delete acquisition {acquisition_id} by user {user.username}")
        
        if not user.is_superuser:
            raise ValidationError("Faqat administratorlar xaridni o'chira oladi.")
        
        acquisition = get_object_or_404(Acquisition, pk=acquisition_id, is_active=True)
        print(f"DEBUG: Found active acquisition - Initial: {acquisition.initial_quantity}, Available: {acquisition.available_quantity}")
        
        with transaction.atomic():
            # Remove supplier debt first
            print(f"DEBUG: Reducing supplier debt: {acquisition.total_amount} {acquisition.currency}")
            acquisition.supplier.reduce_debt(acquisition.total_amount, acquisition.currency)
            
            # Soft delete the acquisition and ticket
            print(f"DEBUG: Soft deleting acquisition and ticket")
            acquisition.soft_delete()
            
            print(f"DEBUG: Soft deletion completed successfully")
            return True

    @staticmethod
    def update_acquisition(original_acquisition, form):
        """Update acquisition with complete business logic handling"""
        with transaction.atomic():
            # Store original values
            original_supplier = original_acquisition.supplier
            original_total_amount = original_acquisition.total_amount
            original_currency = original_acquisition.currency
            original_quantity = original_acquisition.initial_quantity
            
            # Check if tickets were sold and quantity is being reduced
            sold_quantity = original_quantity - original_acquisition.available_quantity
            new_quantity = form.cleaned_data['initial_quantity']
            
            if new_quantity < sold_quantity:
                raise ValidationError(f"Jami miqdorni {new_quantity} ga kamaytirish mumkin emas. {sold_quantity} dona chipta allaqachon sotilgan.")
            
            # Update ticket information
            ticket = original_acquisition.ticket
            ticket.ticket_type = form.cleaned_data['ticket_type']
            ticket.description = form.cleaned_data['ticket_description']
            ticket.departure_date_time = form.cleaned_data['ticket_departure_date_time']
            ticket.arrival_date_time = form.cleaned_data.get('ticket_arrival_date_time')
            ticket.save()
            
            # Update acquisition
            updated_acquisition = form.save(commit=False)
            updated_acquisition.id = original_acquisition.id
            updated_acquisition.ticket = ticket
            
            # Update salesperson if provided
            if 'salesperson' in form.cleaned_data:
                updated_acquisition.salesperson = form.cleaned_data['salesperson']
            
            # Adjust available quantity based on new initial quantity
            quantity_diff = new_quantity - original_quantity
            updated_acquisition.available_quantity = original_acquisition.available_quantity + quantity_diff
            
            updated_acquisition.save()
            
            # Handle supplier debt changes
            AcquisitionService._handle_supplier_changes(
                original_acquisition, original_supplier, original_total_amount, 
                original_currency, updated_acquisition
            )
            
            return updated_acquisition

    @staticmethod
    def _handle_supplier_changes(original_acquisition, original_supplier, original_total_amount, 
                               original_currency, updated_acquisition):
        """Handle supplier debt changes"""
        new_supplier = updated_acquisition.supplier
        new_total_amount = updated_acquisition.total_amount
        new_currency = updated_acquisition.currency
        
        # If supplier changed
        if original_supplier.id != new_supplier.id:
            # Remove debt from original supplier
            original_supplier.reduce_debt(original_total_amount, original_currency)
            
            # Add debt to new supplier
            new_supplier.add_debt(new_total_amount, new_currency)
        else:
            # Same supplier, adjust debt difference
            if original_currency == new_currency:
                debt_diff = new_total_amount - original_total_amount
                if debt_diff != 0:
                    original_supplier.add_debt(debt_diff, new_currency)
            else:
                # Currency changed - remove old debt, add new debt
                original_supplier.reduce_debt(original_total_amount, original_currency)
                original_supplier.add_debt(new_total_amount, new_currency) 