from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.db import transaction
from apps.core.constants import CurrencyChoices, BusinessLimits
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
    class Meta:
        verbose_name = "Ta'minotchi"
        verbose_name_plural = "Ta'minotchilar"
        ordering = ['name']


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
        
        account_field = getattr(self, 'paid_to_account', None) or getattr(self, 'paid_from_account', None)
        if account_field and account_field.currency != self.currency:
            raise ValidationError(
                f"Hisob valyutasi ({account_field.currency}) "
                f"to'lov valyutasi ({self.currency}) bilan mos kelmaydi."
            )

    def __str__(self):
        contact = getattr(self, 'agent', None) or getattr(self, 'supplier', None)
        return f"{contact.name} - {self.amount:,.2f} {self.currency} - {self.payment_date.strftime('%d-%m-%Y')}"


class SupplierPayment(BasePayment):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='payments')
    paid_from_account = models.ForeignKey('accounting.FinancialAccount', on_delete=models.PROTECT)

    def save(self, *args, **kwargs):
        self.full_clean()
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            self.supplier.reduce_debt(self.amount, self.currency)
            self.paid_from_account.current_balance -= self.amount
            self.paid_from_account.save(update_fields=['current_balance', 'updated_at'])

    class Meta(BasePayment.Meta):
        verbose_name = "Ta'minotchi To'lovi"
        verbose_name_plural = "Ta'minotchi To'lovlari"


class AgentPayment(BasePayment):
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='payments')
    paid_to_account = models.ForeignKey('accounting.FinancialAccount', on_delete=models.PROTECT)

    def save(self, *args, **kwargs):
        self.full_clean()
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            self.agent.reduce_debt(self.amount, self.currency)
            self.paid_to_account.current_balance += self.amount
            self.paid_to_account.save(update_fields=['current_balance', 'updated_at'])

    class Meta(BasePayment.Meta):
        verbose_name = "Agent To'lovi"
        verbose_name_plural = "Agent To'lovlari"