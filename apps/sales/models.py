from django.db import models
from django.utils import timezone
from apps.inventory.models import Acquisition
from apps.accounting.models import FinancialAccount
from apps.core.models import Salesperson
from decimal import Decimal
from django.core.exceptions import ValidationError


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

    @property
    def returned_quantity(self):
        """Get total quantity returned for this sale"""
        return self.returns.aggregate(
            total=models.Sum('quantity_returned')
        )['total'] or 0

    @property
    def remaining_quantity(self):
        """Get remaining quantity that can be returned"""
        return self.quantity - self.returned_quantity

    @property
    def has_returns(self):
        """Check if this sale has any returns"""
        return self.returns.exists()

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


class TicketReturn(models.Model):
    """Model to handle ticket returns with fines"""
    
    # Related sale
    original_sale = models.ForeignKey(
        Sale,
        on_delete=models.PROTECT,
        related_name='returns',
        verbose_name="Asosiy sotuv"
    )
    
    # Return details
    return_date = models.DateTimeField(default=timezone.now, verbose_name="Qaytarish sanasi")
    quantity_returned = models.PositiveIntegerField(verbose_name="Qaytarilgan miqdori")
    
    # Fine details
    fine_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Mijoz/Agent jarimasi"
    )
    fine_currency = models.CharField(
        max_length=3,
        choices=Sale.SaleCurrency.choices,
        verbose_name="Jarima valyutasi"
    )
    
    # Supplier fine details
    supplier_fine_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Ta'minotchi jarimasi"
    )
    supplier_fine_currency = models.CharField(
        max_length=3,
        choices=Sale.SaleCurrency.choices,
        verbose_name="Ta'minotchi jarima valyutasi"
    )
    
    # Payment tracking
    fine_paid_to_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='return_fines_received',
        verbose_name="Jarima to'lov hisobi"
    )
    
    # Notes
    notes = models.TextField(blank=True, null=True, verbose_name="Izohlar")
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Chipta qaytarishi"
        verbose_name_plural = "Chipta qaytarishlari"
        ordering = ['-return_date', '-created_at']
    
    def clean(self):
        super().clean()
        if self.quantity_returned > self.original_sale.remaining_quantity:
            raise ValidationError(
                f"Qaytarilgan miqdor ({self.quantity_returned}) qolgan miqdordan ({self.original_sale.remaining_quantity}) ko'p bo'lishi mumkin emas."
            )
        
        if self.fine_amount < 0:
            raise ValidationError("Jarima miqdori manfiy bo'lishi mumkin emas.")
        
        if self.supplier_fine_amount < 0:
            raise ValidationError("Ta'minotchi jarima miqdori manfiy bo'lishi mumkin emas.")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Qaytarish #{self.id}: {self.quantity_returned} dona - {self.original_sale}"
    
    @property
    def is_agent_return(self):
        """Check if this is an agent return"""
        return self.original_sale.agent is not None
    
    @property
    def is_customer_return(self):
        """Check if this is a customer return"""
        return self.original_sale.agent is None
    
    @property
    def total_fine_amount(self):
        """Total fine amount in return currency"""
        return self.fine_amount * self.quantity_returned
    
    @property
    def total_supplier_fine_amount(self):
        """Total supplier fine amount in supplier fine currency"""
        return self.supplier_fine_amount * self.quantity_returned
    
    @property
    def returned_sale_amount(self):
        """Amount that was returned (original sale price * quantity returned)"""
        return self.original_sale.unit_sale_price * self.quantity_returned
    
    @property
    def returned_acquisition_amount(self):
        """Amount that was returned based on original acquisition price (what we paid to supplier)"""
        return self.original_sale.related_acquisition.unit_price * self.quantity_returned