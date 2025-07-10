from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.core.constants import CurrencyChoices


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
        if currency == CurrencyChoices.UZS:
            self.balance_uzs += amount
        elif currency == CurrencyChoices.USD:
            self.balance_usd += amount
        self.save(update_fields=['balance_uzs', 'balance_usd', 'updated_at'])

    def reduce_debt(self, amount, currency):
        if currency == CurrencyChoices.UZS:
            self.balance_uzs -= amount
        elif currency == CurrencyChoices.USD:
            self.balance_usd -= amount
        self.save(update_fields=['balance_uzs', 'balance_usd', 'updated_at'])

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


class Agent(BaseContact):
    class Meta:
        verbose_name = "Agent"
        verbose_name_plural = "Agentlar"
        ordering = ['name']


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