from decimal import Decimal
from django.core.exceptions import ValidationError
from apps.core.constants import CurrencyChoices


class TicketValidator:
    """Centralized validation for tickets"""

    @staticmethod
    def validate_ticket_data(ticket_type, description, departure_date_time, arrival_date_time=None):
        """Validate ticket creation data"""
        if not ticket_type:
            raise ValidationError("Ticket type is required.")
        
        if not description or not description.strip():
            raise ValidationError("Ticket description is required.")
        
        if not departure_date_time:
            raise ValidationError("Departure date and time is required.")
        
        if arrival_date_time and arrival_date_time <= departure_date_time:
            raise ValidationError("Arrival time must be after departure time.")
        
        return {
            'ticket_type': ticket_type,
            'description': description.strip(),
            'departure_date_time': departure_date_time,
            'arrival_date_time': arrival_date_time
        }


class AcquisitionValidator:
    """Centralized validation for acquisitions"""

    @staticmethod
    def validate_quantity(initial_quantity):
        """Validate quantity values"""
        if not initial_quantity or initial_quantity <= 0:
            raise ValidationError("Initial quantity must be greater than 0.")
        
        return initial_quantity

    @staticmethod
    def validate_currency_and_prices(transaction_currency, unit_price_uzs, unit_price_usd):
        """Validate currency selection and corresponding prices"""
        if transaction_currency not in [choice[0] for choice in CurrencyChoices.choices]:
            raise ValidationError(f"Invalid transaction currency: {transaction_currency}")
        
        if transaction_currency == CurrencyChoices.UZS:
            if not unit_price_uzs or unit_price_uzs <= 0:
                raise ValidationError("Unit price in UZS must be provided and greater than 0 for UZS transactions.")
            # Clear USD price for UZS transactions
            return transaction_currency, unit_price_uzs, None
            
        elif transaction_currency == CurrencyChoices.USD:
            if not unit_price_usd or unit_price_usd <= 0:
                raise ValidationError("Unit price in USD must be provided and greater than 0 for USD transactions.")
            # Clear UZS price for USD transactions
            return transaction_currency, None, unit_price_usd
        
        raise ValidationError("Transaction currency must be specified.")

    @staticmethod
    def validate_payment_account_currency(paid_from_account, transaction_currency):
        """Validate that payment account currency matches transaction currency"""
        if paid_from_account and paid_from_account.currency != transaction_currency:
            raise ValidationError(
                f"The currency of the selected payment account ({paid_from_account.currency}) "
                f"does not match the transaction currency ({transaction_currency})."
            )

    @staticmethod
    def validate_supplier(supplier):
        """Validate supplier selection"""
        if not supplier:
            raise ValidationError("Supplier is required.")
        return supplier

    @staticmethod
    def validate_stock_availability(acquisition, quantity_requested, current_sale_id=None):
        """Validate stock availability for sales"""
        if not acquisition:
            raise ValidationError("Acquisition batch is required.")
        
        effective_available_qty = acquisition.available_quantity
        
        # For sale updates, add back the original quantity from this sale
        if current_sale_id:
            try:
                from django.apps import apps
                Sale = apps.get_model('sales', 'Sale')
                original_sale = Sale.objects.get(pk=current_sale_id)
                if original_sale.related_acquisition_id == acquisition.id:
                    effective_available_qty += original_sale.quantity
            except:
                pass  # If sale doesn't exist, proceed with current available quantity
        
        if quantity_requested > effective_available_qty:
            raise ValidationError(
                f"Cannot sell {quantity_requested}. Only {effective_available_qty} available from this batch."
            )
        
        return effective_available_qty

    @staticmethod
    def validate_acquisition_data(supplier, acquisition_date, initial_quantity, transaction_currency, 
                                  unit_price_uzs, unit_price_usd, paid_from_account=None):
        """Main validation method for acquisitions"""
        
        # Validate supplier
        supplier = AcquisitionValidator.validate_supplier(supplier)
        
        # Validate quantity
        initial_quantity = AcquisitionValidator.validate_quantity(initial_quantity)
        
        # Validate currency and prices
        transaction_currency, unit_price_uzs, unit_price_usd = AcquisitionValidator.validate_currency_and_prices(
            transaction_currency, unit_price_uzs, unit_price_usd
        )
        
        # Validate payment account currency match
        if paid_from_account:
            AcquisitionValidator.validate_payment_account_currency(paid_from_account, transaction_currency)
        
        return {
            'supplier': supplier,
            'acquisition_date': acquisition_date,
            'initial_quantity': initial_quantity,
            'transaction_currency': transaction_currency,
            'unit_price_uzs': unit_price_uzs,
            'unit_price_usd': unit_price_usd,
            'paid_from_account': paid_from_account
        }


class StockValidator:
    """Centralized validation for stock operations"""

    @staticmethod
    def validate_sale_quantity(acquisition, quantity_to_sell, existing_sale_id=None):
        """Validate that enough stock is available for sale"""
        return AcquisitionValidator.validate_stock_availability(
            acquisition, quantity_to_sell, existing_sale_id
        )

    @staticmethod
    def validate_stock_adjustment(acquisition, new_initial_quantity):
        """Validate stock quantity adjustments"""
        if new_initial_quantity < 0:
            raise ValidationError("Initial quantity cannot be negative.")
        
        # Calculate how many tickets have been sold
        sold_quantity = acquisition.initial_quantity - acquisition.available_quantity
        
        if new_initial_quantity < sold_quantity:
            raise ValidationError(
                f"Cannot reduce initial quantity to {new_initial_quantity}. "
                f"Already sold {sold_quantity} tickets from this batch."
            )
        
        return new_initial_quantity 