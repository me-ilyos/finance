from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.core.constants import CurrencyChoices
from apps.accounting.models import FinancialAccount


class Ticket(models.Model):
    class TicketType(models.TextChoices):
        AIR_TICKET = 'AIR', 'Chipta'
        TOUR_TICKET = 'TOUR', 'Tur paket'
        UMRA_TICKET = 'UMRA', 'Umra'

    ticket_type = models.CharField(max_length=4, choices=TicketType.choices)
    description = models.TextField(help_text="E.g., Destination for air ticket, name/details for tour ticket")
    departure_date_time = models.DateTimeField()
    arrival_date_time = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_ticket_type_display()} - {self.description}"


class Acquisition(models.Model):
    supplier = models.ForeignKey(
        'contacts.Supplier',
        on_delete=models.PROTECT,
        related_name='acquisitions'
    )
    ticket = models.ForeignKey(Ticket, on_delete=models.PROTECT, related_name='acquisitions')
    acquisition_date = models.DateTimeField(default=timezone.now)
    
    salesperson = models.ForeignKey(
        'core.Salesperson',
        on_delete=models.PROTECT,
        related_name='acquisitions_made',
        null=True,
        blank=True,
        help_text="Bu xaridni amalga oshirgan sotuvchi"
    )
    
    # Simplified quantity tracking
    initial_quantity = models.PositiveIntegerField(help_text="Initial quantity acquired")
    available_quantity = models.PositiveIntegerField(help_text="Available quantity for sale", default=0, editable=False)
    
    # Simplified pricing - single price and currency
    unit_price = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CurrencyChoices.choices)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, editable=False)
    
    paid_from_account = models.ForeignKey(
        FinancialAccount, 
        on_delete=models.PROTECT, 
        related_name='acquisitions_paid', 
        blank=True,
        null=True
    )
    notes = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Calculate total amount
        self.total_amount = self.unit_price * self.initial_quantity
        
        # Set available quantity for new acquisitions
        if not self.pk:
            self.available_quantity = self.initial_quantity
        
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.supplier.name} - {self.ticket.description} ({self.available_quantity}/{self.initial_quantity})"
    
    def get_commission_display(self):
        """Return formatted string for commission form dropdown"""
        currency_symbol = "UZS" if self.currency == 'UZS' else "$"
        return (f"{self.acquisition_date.strftime('%d.%m.%Y')} - "
                f"{self.ticket.description[:40]}... - "
                f"{currency_symbol} {self.total_amount:,.2f}")

    def reduce_stock(self, quantity_sold):
        """Reduce available quantity when tickets are sold"""
        if quantity_sold > self.available_quantity:
            raise ValidationError(
                f"Cannot sell {quantity_sold}. Only {self.available_quantity} available."
            )
        
        self.available_quantity -= quantity_sold
        self.save(update_fields=['available_quantity', 'updated_at'])

    def restore_stock(self, quantity_to_restore):
        """Restore available quantity when sale is cancelled/updated"""
        self.available_quantity = min(
            self.available_quantity + quantity_to_restore,
            self.initial_quantity
        )
        self.save(update_fields=['available_quantity', 'updated_at'])

    def can_be_deleted(self):
        """Check if acquisition can be safely deleted (soft delete)"""
        return self.available_quantity == self.initial_quantity

    def soft_delete(self):
        """Mark acquisition and its ticket as inactive instead of deleting"""
        if not self.can_be_deleted():
            sold_quantity = self.initial_quantity - self.available_quantity
            raise ValidationError(f"Bu xariddan {sold_quantity} dona chipta sotilgan. Xaridni o'chirib bo'lmaydi.")
        
        self.is_active = False
        self.ticket.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])
        self.ticket.save(update_fields=['is_active', 'updated_at'])
