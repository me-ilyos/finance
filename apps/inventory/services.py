from django.db import transaction
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from .models import Acquisition, Ticket
from .forms import AcquisitionForm
from apps.contacts.models import SupplierPayment


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
            acquisition.save()
            
            # Step 1: Always add debt to supplier
            acquisition.supplier.add_debt(acquisition.total_amount, acquisition.currency)
            
            # Step 2: If automatic payment, create payment record
            if acquisition.paid_from_account:
                SupplierPayment.objects.create(
                    supplier=acquisition.supplier,
                    payment_date=acquisition.acquisition_date,
                    amount=acquisition.total_amount,
                    currency=acquisition.currency,
                    paid_from_account=acquisition.paid_from_account,
                    notes=f"Avtomatik to'lov - Xarid #{acquisition.pk}"
                )
            
            return acquisition

    @staticmethod
    def delete_acquisition(acquisition_id, user):
        """Delete acquisition with complete transaction rollback"""
        if not user.is_superuser:
            raise ValidationError("Faqat administratorlar xaridni o'chira oladi.")
        
        acquisition = get_object_or_404(Acquisition, pk=acquisition_id)
        
        # Check if tickets were sold
        if acquisition.available_quantity < acquisition.initial_quantity:
            sold_quantity = acquisition.initial_quantity - acquisition.available_quantity
            raise ValidationError(f"Bu xariddan {sold_quantity} dona chipta sotilgan. Xaridni o'chirib bo'lmaydi.")
        
        with transaction.atomic():
            # Remove supplier debt
            acquisition.supplier.reduce_debt(acquisition.total_amount, acquisition.currency)
            
            # If there was automatic payment, remove it
            if acquisition.paid_from_account:
                try:
                    payment = SupplierPayment.objects.get(
                        supplier=acquisition.supplier,
                        amount=acquisition.total_amount,
                        currency=acquisition.currency,
                        notes__contains=f"Xarid #{acquisition.pk}"
                    )
                    payment.delete()
                except SupplierPayment.DoesNotExist:
                    pass
            
            # Delete associated ticket
            if acquisition.ticket:
                acquisition.ticket.delete()
            
            # Delete the acquisition
            acquisition.delete()
            
            return True

    @staticmethod
    def update_acquisition(original_acquisition, form):
        """Update acquisition with complete business logic handling"""
        with transaction.atomic():
            # Store original values
            original_supplier = original_acquisition.supplier
            original_total_amount = original_acquisition.total_amount
            original_currency = original_acquisition.currency
            original_paid_account = original_acquisition.paid_from_account
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
            
            # Adjust available quantity based on new initial quantity
            quantity_diff = new_quantity - original_quantity
            updated_acquisition.available_quantity = original_acquisition.available_quantity + quantity_diff
            
            updated_acquisition.save()
            
            # Handle supplier debt changes
            AcquisitionService._handle_supplier_changes(
                original_acquisition, original_supplier, original_total_amount, 
                original_currency, original_paid_account,
                updated_acquisition
            )
            
            return updated_acquisition

    @staticmethod
    def _handle_supplier_changes(original_acquisition, original_supplier, original_total_amount, 
                               original_currency, original_paid_account, updated_acquisition):
        """Handle supplier and payment changes"""
        new_supplier = updated_acquisition.supplier
        new_total_amount = updated_acquisition.total_amount
        new_currency = updated_acquisition.currency
        new_paid_account = updated_acquisition.paid_from_account
        
        # If supplier changed
        if original_supplier.id != new_supplier.id:
            # Remove debt from original supplier
            original_supplier.reduce_debt(original_total_amount, original_currency)
            
            # Add debt to new supplier
            new_supplier.add_debt(new_total_amount, new_currency)
            
            # Handle payment changes
            AcquisitionService._handle_payment_changes(
                original_acquisition, original_paid_account, original_total_amount, original_currency,
                updated_acquisition, new_paid_account, new_total_amount, new_currency
            )
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
            
            # Handle payment changes
            AcquisitionService._handle_payment_changes(
                original_acquisition, original_paid_account, original_total_amount, original_currency,
                updated_acquisition, new_paid_account, new_total_amount, new_currency
            )

    @staticmethod
    def _handle_payment_changes(original_acquisition, original_paid_account, original_total_amount, original_currency,
                              updated_acquisition, new_paid_account, new_total_amount, new_currency):
        """Handle automatic payment changes"""
        # Remove original payment if it existed
        if original_paid_account:
            try:
                payment = SupplierPayment.objects.get(
                    supplier=original_acquisition.supplier,
                    amount=original_total_amount,
                    currency=original_currency,
                    notes__contains=f"Xarid #{original_acquisition.pk}"
                )
                payment.delete()
            except SupplierPayment.DoesNotExist:
                pass
        
        # Create new payment if needed
        if new_paid_account:
            SupplierPayment.objects.create(
                supplier=updated_acquisition.supplier,
                payment_date=updated_acquisition.acquisition_date,
                amount=new_total_amount,
                currency=new_currency,
                paid_from_account=new_paid_account,
                notes=f"Avtomatik to'lov - Xarid #{updated_acquisition.pk}"
            ) 