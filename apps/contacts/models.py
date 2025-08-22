from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.core.constants import CurrencyChoices
import logging

logger = logging.getLogger(__name__)


class BaseContact(models.Model):
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    initial_balance_uzs = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    initial_balance_usd = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    
    balance_uzs = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    balance_usd = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.pk:
            self.initial_balance_uzs = self.balance_uzs
            self.initial_balance_usd = self.balance_usd
        super().save(*args, **kwargs)

    def add_debt(self, amount, currency):
        logger.info(f"add_debt called for {self.__class__.__name__} {self.id} ({self.name})")
        logger.info(f"  Adding {amount} {currency}")
        logger.info(f"  Balance before: UZS={self.balance_uzs}, USD={self.balance_usd}")
        
        if currency == CurrencyChoices.UZS:
            old_balance = self.balance_uzs
            self.balance_uzs += amount
            logger.info(f"  UZS balance changed from {old_balance} to {self.balance_uzs}")
        elif currency == CurrencyChoices.USD:
            old_balance = self.balance_usd
            self.balance_usd += amount
            logger.info(f"  USD balance changed from {old_balance} to {self.balance_usd}")
        
        self.save(update_fields=['balance_uzs', 'balance_usd', 'updated_at'])
        logger.info(f"  Balance after save: UZS={self.balance_uzs}, USD={self.balance_usd}")

    def reduce_debt(self, amount, currency):
        logger.info(f"reduce_debt called for {self.__class__.__name__} {self.id} ({self.name})")
        logger.info(f"  Reducing {amount} {currency}")
        logger.info(f"  Balance before: UZS={self.balance_uzs}, USD={self.balance_usd}")
        
        if currency == CurrencyChoices.UZS:
            old_balance = self.balance_uzs
            self.balance_uzs -= amount
            logger.info(f"  UZS balance changed from {old_balance} to {self.balance_uzs}")
        elif currency == CurrencyChoices.USD:
            old_balance = self.balance_usd
            self.balance_usd -= amount
            logger.info(f"  USD balance changed from {old_balance} to {self.balance_usd}")
        
        self.save(update_fields=['balance_uzs', 'balance_usd', 'updated_at'])
        logger.info(f"  Balance after save: UZS={self.balance_uzs}, USD={self.balance_usd}")

    def __str__(self):
        return self.name


class Supplier(BaseContact):
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    
    class Meta:
        verbose_name = "Ta'minotchi"
        verbose_name_plural = "Ta'minotchilar"
        ordering = ['name']

    def can_be_deactivated(self):
        """Check if supplier can be deactivated (when there's no debt on both sides)"""
        return self.balance_uzs == 0 and self.balance_usd == 0
    
    def recalculate_balance(self):
        """Recalculate supplier balance based on all transactions"""
        from django.db.models import Sum
        
        # Calculate UZS balance
        uzs_acquisitions = self.acquisitions.filter(currency='UZS', is_active=True).aggregate(
            total=Sum('total_amount'))['total'] or 0
        uzs_payments = self.payments.filter(currency='UZS').aggregate(
            total=Sum('amount'))['total'] or 0
        uzs_commissions = self.commissions.filter(currency='UZS').aggregate(
            total=Sum('amount'))['total'] or 0
        
        # Calculate USD balance  
        usd_acquisitions = self.acquisitions.filter(currency='USD', is_active=True).aggregate(
            total=Sum('total_amount'))['total'] or 0
        usd_payments = self.payments.filter(currency='USD').aggregate(
            total=Sum('amount'))['total'] or 0
        usd_commissions = self.commissions.filter(currency='USD').aggregate(
            total=Sum('amount'))['total'] or 0
        
        # Update balances: Initial + Acquisitions - Commissions - Payments
        self.balance_uzs = (self.initial_balance_uzs or 0) + uzs_acquisitions - uzs_commissions - uzs_payments
        self.balance_usd = (self.initial_balance_usd or 0) + usd_acquisitions - usd_commissions - usd_payments
        
        self.save(update_fields=['balance_uzs', 'balance_usd', 'updated_at'])
        return self.balance_uzs, self.balance_usd


class Agent(BaseContact):
    class Meta:
        verbose_name = "Agent"
        verbose_name_plural = "Agentlar"
        ordering = ['name']


class Commission(models.Model):
    supplier = models.ForeignKey(
        Supplier, 
        on_delete=models.CASCADE, 
        related_name='commissions',
        verbose_name="Ta'minotchi"
    )
    acquisition = models.ForeignKey(
        'inventory.Acquisition',
        on_delete=models.CASCADE,
        related_name='commissions',
        verbose_name="Xarid"
    )
    commission_date = models.DateTimeField(default=timezone.now, verbose_name="Komissiya Sanasi")
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Komissiya Miqdori")
    currency = models.CharField(max_length=3, choices=CurrencyChoices.choices, verbose_name="Valyuta")
    notes = models.TextField(blank=True, null=True, verbose_name="Izohlar")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Komissiya"
        verbose_name_plural = "Komissiyalar"
        ordering = ['-commission_date']

    def clean(self):
        super().clean()
        if self.amount <= 0:
            raise ValidationError("Komissiya miqdori musbat bo'lishi kerak.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.supplier.name} - {self.amount:,.2f} {self.currency} - {self.commission_date.strftime('%d-%m-%Y')}"


class BasePayment(models.Model):
    payment_date = models.DateTimeField(default=timezone.now)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CurrencyChoices.choices)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ['-payment_date']

    def clean(self):
        super().clean()
        if self.amount <= 0:
            raise ValidationError("To'lov miqdori musbat bo'lishi kerak.")

    def __str__(self):
        contact = getattr(self, 'agent', None) or getattr(self, 'supplier', None)
        return f"{contact.name} - {self.amount:,.2f} {self.currency} - {self.payment_date.strftime('%d-%m-%Y')}"


class SupplierPayment(BasePayment):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='payments')
    paid_from_account = models.ForeignKey('accounting.FinancialAccount', on_delete=models.PROTECT)

    class Meta(BasePayment.Meta):
        verbose_name = "Ta'minotchi To'lovi"
        verbose_name_plural = "Ta'minotchi To'lovlari"


class AgentPayment(BasePayment):
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='payments')
    paid_to_account = models.ForeignKey('accounting.FinancialAccount', on_delete=models.PROTECT)
    
    # Cross-currency payment fields
    exchange_rate = models.DecimalField(
        max_digits=10, 
        decimal_places=4, 
        null=True, 
        blank=True,
        help_text="UZS per 1 USD exchange rate (only for cross-currency payments)"
    )
    original_amount = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Original amount in the currency paid (before conversion)"
    )
    original_currency = models.CharField(
        max_length=3, 
        choices=CurrencyChoices.choices, 
        null=True, 
        blank=True,
        help_text="Original currency paid (before conversion)"
    )

    def is_cross_currency_payment(self):
        """Check if this is a cross-currency payment"""
        return self.exchange_rate is not None and self.original_amount is not None

    def __str__(self):
        if self.is_cross_currency_payment():
            if self.original_currency == 'USD':
                # USD to UZS conversion
                return f"{self.agent.name} - ${self.original_amount:,.2f} -> {self.amount:,.0f} UZS (Rate: {self.exchange_rate:,.0f}) - {self.payment_date.strftime('%d-%m-%Y')}"
            else:
                # UZS to USD conversion
                return f"{self.agent.name} - {self.original_amount:,.0f} UZS -> ${self.amount:,.2f} (Rate: {self.exchange_rate:,.0f}) - {self.payment_date.strftime('%d-%m-%Y')}"
        else:
            return f"{self.agent.name} - {self.amount:,.2f} {self.currency} - {self.payment_date.strftime('%d-%m-%Y')}"

    class Meta(BasePayment.Meta):
        verbose_name = "Agent To'lovi"
        verbose_name_plural = "Agent To'lovlari"


class SupplierBalanceAdjustment(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='adjustments')
    adjustment_date = models.DateTimeField(default=timezone.now)
    amount = models.DecimalField(max_digits=20, decimal_places=2, help_text="Signed amount. Positive increases our debt to supplier.")
    currency = models.CharField(max_length=3, choices=CurrencyChoices.choices)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-adjustment_date', '-created_at']
        verbose_name = "Ta'minotchi Balans Tuzatish"
        verbose_name_plural = "Ta'minotchi Balans Tuzatishlar"

    def __str__(self):
        sign = '+' if self.amount >= 0 else ''
        return f"{self.supplier.name} {sign}{self.amount:,.2f} {self.currency} ({self.adjustment_date.strftime('%d-%m-%Y')})"


class AgentBalanceAdjustment(models.Model):
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='adjustments')
    adjustment_date = models.DateTimeField(default=timezone.now)
    amount = models.DecimalField(max_digits=20, decimal_places=2, help_text="Signed amount. Positive increases agent's debt to us.")
    currency = models.CharField(max_length=3, choices=CurrencyChoices.choices)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-adjustment_date', '-created_at']
        verbose_name = "Agent Balans Tuzatish"
        verbose_name_plural = "Agent Balans Tuzatishlar"

    def __str__(self):
        sign = '+' if self.amount >= 0 else ''
        return f"{self.agent.name} {sign}{self.amount:,.2f} {self.currency} ({self.adjustment_date.strftime('%d-%m-%Y')})"