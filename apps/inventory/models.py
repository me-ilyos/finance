from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from django.db import transaction
from apps.accounting.models import FinancialAccount
import logging

logger = logging.getLogger(__name__)


class Ticket(models.Model):
    class TicketType(models.TextChoices):
        AIR_TICKET = 'AIR', 'Air Ticket'
        TOUR_TICKET = 'TOUR', 'Tour Ticket'

    ticket_type = models.CharField(max_length=4, choices=TicketType.choices)
    identifier = models.CharField(max_length=255, unique=True, blank=True, help_text="Unique identifier for this ticket type/batch. Auto-generated if left blank.")
    description = models.TextField(help_text="E.g., Destination for air ticket, name/details for tour ticket")
    departure_date_time = models.DateTimeField()
    arrival_date_time = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        """Save ticket - identifier generation handled by service layer"""
        super().save(*args, **kwargs)

    def __str__(self):
        return self.identifier or f"Ticket {self.id}"


class Acquisition(models.Model):
    supplier = models.ForeignKey(
        'contacts.Supplier',
        on_delete=models.PROTECT,
        related_name='acquisitions_from_supplier'
    )
    ticket = models.ForeignKey(Ticket, on_delete=models.PROTECT, related_name='acquisitions')
    acquisition_date = models.DateTimeField(default=timezone.now)
    initial_quantity = models.PositiveIntegerField(help_text="Initial quantity acquired in this batch.")
    available_quantity = models.PositiveIntegerField(help_text="Available quantity from this batch for sale. Updated by sales operations.", default=0, editable=False)

    class Currency(models.TextChoices):
        UZS = 'UZS', 'Uzbek Som'
        USD = 'USD', 'US Dollar'

    # Prices are per unit
    unit_price_uzs = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    unit_price_usd = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    
    transaction_currency = models.CharField(max_length=3, choices=Currency.choices, help_text="Currency of this transaction (unit price and total)")
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, editable=False, help_text="Automatically calculated based on original quantity and unit price.")
    
    paid_from_account = models.ForeignKey(
        FinancialAccount, 
        on_delete=models.PROTECT, 
        related_name='acquisitions_paid', 
        blank=True,
        null=True
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """Basic model validation - complex business logic handled by validators"""
        super().clean()
        
        # Basic currency validation
        if self.transaction_currency == self.Currency.UZS:
            if not self.unit_price_uzs:
                raise ValidationError({'unit_price_uzs': 'Unit price in UZS must be provided if transaction currency is UZS.'})
        elif self.transaction_currency == self.Currency.USD:
            if not self.unit_price_usd:
                raise ValidationError({'unit_price_usd': 'Unit price in USD must be provided if transaction currency is USD.'})

    def save(self, *args, **kwargs):
        """Save acquisition and update related records"""
        self.full_clean()
        is_new = self.pk is None
        
        # Calculate total amount
        if self.transaction_currency == self.Currency.UZS and self.unit_price_uzs:
            self.total_amount = self.unit_price_uzs * self.initial_quantity
        elif self.transaction_currency == self.Currency.USD and self.unit_price_usd:
            self.total_amount = self.unit_price_usd * self.initial_quantity
        
        # Set available quantity to initial quantity for new acquisitions
        if is_new:
            self.available_quantity = self.initial_quantity
        
        super().save(*args, **kwargs)
        
        # Update related records for new acquisitions
        if is_new:
            self._update_related_records()

    def _update_related_records(self):
        """Update supplier balance and financial account for new acquisition"""
        try:
            with transaction.atomic():
                # If payment account is specified, this is a paid acquisition (no debt created)
                if self.paid_from_account:
                    # Only update financial account - no debt to supplier since it's paid
                    self.paid_from_account.current_balance -= self.total_amount
                    self.paid_from_account.save(update_fields=['current_balance', 'updated_at'])
                    logger.info(f"Paid acquisition {self.id}: Updated financial account {self.paid_from_account.id}, no debt created")
                else:
                    # No payment made - create debt with supplier
                    self.supplier.update_balance_on_acquisition(self.total_amount, self.transaction_currency)
                    logger.info(f"Unpaid acquisition {self.id}: Created debt of {self.total_amount} {self.transaction_currency} with supplier {self.supplier.id}")
                
        except Exception as e:
            logger.error(f"Error updating related records for acquisition {self.pk}: {e}")
            raise

    def __str__(self):
        return f"{self.supplier.name} - {self.ticket.description} ({self.available_quantity}/{self.initial_quantity})"
