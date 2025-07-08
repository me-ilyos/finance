from django.db import models
from django.utils import timezone
from apps.inventory.models import Acquisition
from apps.accounting.models import FinancialAccount
from apps.core.models import Salesperson
from decimal import Decimal


class Sale(models.Model):
    class SaleCurrency(models.TextChoices):
        UZS = 'UZS', 'Uzbek Som'
        USD = 'USD', 'US Dollar'

    sale_date = models.DateTimeField(default=timezone.now)
    quantity = models.PositiveIntegerField()
    related_acquisition = models.ForeignKey(
        Acquisition, 
        on_delete=models.PROTECT,
        related_name='sales_from_this_batch'
    )

    salesperson = models.ForeignKey(
        Salesperson,
        on_delete=models.PROTECT,
        related_name='sales_made',
        null=True,
        blank=True,
        help_text="Bu sotuvni amalga oshirgan sotuvchi"
    )

    agent = models.ForeignKey(
        'contacts.Agent',
        on_delete=models.PROTECT, 
        null=True, 
        blank=True, 
        related_name='agent_sales'
    )
    client_full_name = models.CharField(max_length=255, null=True, blank=True)
    client_id_number = models.CharField(max_length=50, null=True, blank=True)

    unit_sale_price = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        help_text="Price per unit in the transaction currency."
    )
    sale_currency = models.CharField(
        max_length=3, 
        choices=SaleCurrency.choices, 
        editable=False
    )
    total_sale_amount = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        editable=False, 
        help_text="Total amount for this sale."
    )
    
    profit = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        editable=False, 
        default=Decimal('0.00'), 
        help_text="Profit from this sale in transaction currency."
    )

    paid_to_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        null=True, 
        blank=True, 
        related_name='sale_payments_received',
        help_text="Account that received the payment for direct sales to clients."
    )


    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_fully_paid(self):
        """Check if sale is fully paid"""
        if self.agent:
            # For agent sales, payment is tracked in agent's overall balance
            return False  # Always show as unpaid since it's tracked separately
        else:
            # For direct client sales, check if payment account is set
            return self.paid_to_account is not None

    def clean(self):
        """Basic model validation - detailed validation handled by forms"""
        super().clean()
        
        # Set sale currency from acquisition
        if self.related_acquisition:
            self.sale_currency = self.related_acquisition.currency

    def save(self, *args, **kwargs):
        """Save sale - business logic handled by service layer"""
        # Only set currency if not already set (service layer handles this)
        if self.related_acquisition and not self.sale_currency:
            self.sale_currency = self.related_acquisition.currency
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Delete sale - business logic handled by service layer"""
        super().delete(*args, **kwargs)

    def __str__(self):
        buyer_info = "Agent sotishi" if self.agent_id else (self.client_full_name or "To'g'ridan-to'g'ri sotuv")
        sale_date_str = self.sale_date.strftime('%d.%m.%Y') if self.sale_date else 'Sana yo\'q'
        return f"Sotuv #{self.id}: {self.quantity} dona {buyer_info} ga {sale_date_str}"

    class Meta:
        verbose_name = "Sale"
        verbose_name_plural = "Sales"
        ordering = ['-sale_date', '-created_at']