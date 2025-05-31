import logging
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.utils import timezone
from apps.core.constants import CurrencyChoices

logger = logging.getLogger(__name__)


class TicketService:
    """Service class for ticket operations"""

    @staticmethod
    def generate_identifier(ticket_type, description, departure_date_time):
        """Generate unique identifier for ticket"""
        parts = [ticket_type.upper().replace(" ", "_")]
        
        if description:
            slugified_desc = slugify(description)
            parts.append(slugified_desc[:50] if len(slugified_desc) > 50 else slugified_desc)
        
        if departure_date_time:
            parts.append(departure_date_time.strftime('%Y%m%d%H%M'))
        
        base_identifier = "-".join(filter(None, parts))
        
        # Ensure uniqueness
        from .models import Ticket
        identifier = base_identifier
        counter = 1
        while Ticket.objects.filter(identifier=identifier).exists():
            identifier = f"{base_identifier}-{counter}"
            counter += 1
            
        return identifier

    @staticmethod
    def create_ticket(ticket_data):
        """Create a new ticket with auto-generated identifier"""
        from .models import Ticket
        
        try:
            if not ticket_data.get('identifier'):
                ticket_data['identifier'] = TicketService.generate_identifier(
                    ticket_data['ticket_type'],
                    ticket_data['description'],
                    ticket_data['departure_date_time']
                )
            
            ticket = Ticket.objects.create(**ticket_data)
            logger.info(f"Created ticket {ticket.identifier}")
            return ticket
            
        except Exception as e:
            logger.error(f"Error creating ticket: {e}")
            raise


class AcquisitionService:
    """Service class for acquisition operations"""

    @staticmethod
    def calculate_total_amount(initial_quantity, unit_price_uzs, unit_price_usd, transaction_currency):
        """Calculate total amount based on currency and unit price"""
        if transaction_currency == CurrencyChoices.UZS and unit_price_uzs is not None:
            return initial_quantity * unit_price_uzs
        elif transaction_currency == CurrencyChoices.USD and unit_price_usd is not None:
            return initial_quantity * unit_price_usd
        else:
            return Decimal('0.00')

    @staticmethod
    def update_financial_account_for_acquisition(acquisition, original_acquisition=None):
        """Update financial account balance for acquisition payments"""
        from apps.accounting.models import FinancialAccount
        
        try:
            with transaction.atomic():
                # Handle original payment reversal for updates
                if original_acquisition and original_acquisition.paid_from_account_id:
                    if (original_acquisition.paid_from_account_id != acquisition.paid_from_account_id or 
                        original_acquisition.total_amount != acquisition.total_amount):
                        
                        try:
                            old_account = FinancialAccount.objects.select_for_update().get(
                                pk=original_acquisition.paid_from_account_id
                            )
                            old_account.current_balance += original_acquisition.total_amount
                            old_account.save(update_fields=['current_balance', 'updated_at'])
                            logger.info(f"Reverted {original_acquisition.total_amount} to account {old_account.id}")
                        except FinancialAccount.DoesNotExist:
                            logger.warning(f"Original financial account {original_acquisition.paid_from_account_id} not found")

                # Apply new payment deduction
                if acquisition.paid_from_account:
                    if (not original_acquisition or 
                        original_acquisition.paid_from_account_id != acquisition.paid_from_account_id or
                        original_acquisition.total_amount != acquisition.total_amount):
                        
                        account = FinancialAccount.objects.select_for_update().get(
                            pk=acquisition.paid_from_account_id
                        )
                        account.current_balance -= acquisition.total_amount
                        account.save(update_fields=['current_balance', 'updated_at'])
                        logger.info(f"Deducted {acquisition.total_amount} from account {account.id}")

        except Exception as e:
            logger.error(f"Error updating financial account for acquisition {acquisition.id}: {e}")
            raise

    @staticmethod
    def create_acquisition(acquisition_data, ticket_data):
        """Create new acquisition with ticket and financial updates"""
        from .models import Acquisition
        
        try:
            with transaction.atomic():
                # Create ticket first
                ticket = TicketService.create_ticket(ticket_data)
                
                # Prepare acquisition data
                acquisition_data['ticket'] = ticket
                acquisition_data['available_quantity'] = acquisition_data['initial_quantity']
                
                # Calculate total amount
                acquisition_data['total_amount'] = AcquisitionService.calculate_total_amount(
                    acquisition_data['initial_quantity'],
                    acquisition_data.get('unit_price_uzs'),
                    acquisition_data.get('unit_price_usd'),
                    acquisition_data['transaction_currency']
                )
                
                # Create acquisition
                acquisition = Acquisition.objects.create(**acquisition_data)
                
                # Update financial account
                AcquisitionService.update_financial_account_for_acquisition(acquisition)
                
                logger.info(f"Created acquisition {acquisition.id} for ticket {ticket.identifier}")
                return acquisition
                
        except Exception as e:
            logger.error(f"Error creating acquisition: {e}")
            raise

    @staticmethod
    def update_acquisition(acquisition, original_data):
        """Update acquisition with proper quantity and financial adjustments"""
        try:
            with transaction.atomic():
                # Handle quantity changes for available_quantity
                if acquisition.initial_quantity != original_data.get('initial_quantity', 0):
                    quantity_diff = acquisition.initial_quantity - original_data['initial_quantity']
                    acquisition.available_quantity = max(
                        0, 
                        min(
                            acquisition.initial_quantity, 
                            original_data['available_quantity'] + quantity_diff
                        )
                    )
                
                # Recalculate total amount
                acquisition.total_amount = AcquisitionService.calculate_total_amount(
                    acquisition.initial_quantity,
                    acquisition.unit_price_uzs,
                    acquisition.unit_price_usd,
                    acquisition.transaction_currency
                )
                
                # Save acquisition
                acquisition.save()
                
                # Create mock original acquisition for financial account update
                if original_data:
                    from .models import Acquisition
                    original_acquisition = Acquisition(
                        id=acquisition.id,
                        paid_from_account_id=original_data.get('paid_from_account_id'),
                        total_amount=original_data.get('total_amount', Decimal('0.00'))
                    )
                    AcquisitionService.update_financial_account_for_acquisition(acquisition, original_acquisition)
                else:
                    AcquisitionService.update_financial_account_for_acquisition(acquisition)
                
                logger.info(f"Updated acquisition {acquisition.id}")
                return acquisition
                
        except Exception as e:
            logger.error(f"Error updating acquisition {acquisition.id}: {e}")
            raise

    @staticmethod
    def update_stock_for_sale(acquisition_id, quantity_sold):
        """Update available quantity when tickets are sold"""
        from .models import Acquisition
        
        try:
            with transaction.atomic():
                acquisition = Acquisition.objects.select_for_update().get(pk=acquisition_id)
                
                if quantity_sold > acquisition.available_quantity:
                    raise ValidationError(
                        f"Cannot sell {quantity_sold}. Only {acquisition.available_quantity} available."
                    )
                
                acquisition.available_quantity -= quantity_sold
                acquisition.save(update_fields=['available_quantity', 'updated_at'])
                
                logger.info(f"Updated stock for acquisition {acquisition_id}: sold {quantity_sold}")
                return acquisition
                
        except Exception as e:
            logger.error(f"Error updating stock for acquisition {acquisition_id}: {e}")
            raise

    @staticmethod
    def revert_stock_for_sale(acquisition_id, quantity_to_revert):
        """Revert available quantity when sale is cancelled/updated"""
        from .models import Acquisition
        
        try:
            with transaction.atomic():
                acquisition = Acquisition.objects.select_for_update().get(pk=acquisition_id)
                acquisition.available_quantity += quantity_to_revert
                
                # Ensure we don't exceed initial quantity
                acquisition.available_quantity = min(
                    acquisition.available_quantity, 
                    acquisition.initial_quantity
                )
                
                acquisition.save(update_fields=['available_quantity', 'updated_at'])
                
                logger.info(f"Reverted stock for acquisition {acquisition_id}: added back {quantity_to_revert}")
                return acquisition
                
        except Exception as e:
            logger.error(f"Error reverting stock for acquisition {acquisition_id}: {e}")
            raise 