from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.inventory.models import Acquisition
from apps.accounting.models import FinancialAccount
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

    paid_amount_on_this_sale = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Total amount paid specifically towards this sale."
    )

    paid_to_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        null=True, 
        blank=True, 
        related_name='sale_payments_received',
        help_text="Account that received the payment."
    )
    initial_payment_amount = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        help_text="Agent uchun boshlang'ich to'lov miqdori (sotuv valyutasida)."
    )

    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def balance_due_on_this_sale(self):
        """Calculate remaining balance on this sale"""
        return self.total_sale_amount - self.paid_amount_on_this_sale

    @property
    def is_fully_paid(self):
        """Check if sale is fully paid"""
        if self.agent:
            return self.balance_due_on_this_sale <= Decimal('0.00')
        else:
            return self.paid_to_account is not None

    def clean(self):
        """Basic model validation - complex business logic handled by validators"""
        super().clean()
        
        # Basic validation only - detailed validation in validators
        if self.related_acquisition:
            self.sale_currency = self.related_acquisition.transaction_currency
        
        # Basic buyer validation
        if self.agent and (self.client_full_name or self.client_id_number):
            raise ValidationError(
                "Cannot specify both an agent and client details for the same sale."
            )
        
        if not self.agent and not (self.client_full_name and self.client_id_number):
            raise ValidationError(
                "Must specify either an agent or both client full name and ID number."
            )

    def save(self, *args, **kwargs):
        """Save sale - business logic handled by service layer"""
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Delete sale - business logic handled by service layer"""
        super().delete(*args, **kwargs)

    def __str__(self):
        buyer_info = str(self.agent.name) if self.agent else f"{self.client_full_name or 'N/A Client'}"
        ticket_info = (self.related_acquisition.ticket.identifier 
                      if self.related_acquisition and self.related_acquisition.ticket 
                      else f"Acq.ID: {self.related_acquisition_id}")
        sale_date_str = self.sale_date.strftime('%Y-%m-%d') if self.sale_date else 'N/A Date'
        profit_str = str(self.profit) if hasattr(self, 'profit') else "N/A"
        payment_status = "Paid" if self.paid_to_account else ("Owes" if self.agent else "Unpaid")
        
        return (f"Sale: {self.quantity}x {ticket_info} to {buyer_info} on {sale_date_str} "
                f"(Profit: {profit_str} {self.sale_currency}) - {payment_status}")

    class Meta:
        verbose_name = "Sale"
        verbose_name_plural = "Sales"
        ordering = ['-sale_date', '-created_at']
