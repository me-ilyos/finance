from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from apps.accounting.models import FinancialAccount


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
        """Save acquisition - business logic handled by service layer"""
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.supplier.name} - {self.ticket.description} ({self.available_quantity}/{self.initial_quantity})"
