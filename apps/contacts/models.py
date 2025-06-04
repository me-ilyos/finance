from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.db import transaction
from apps.core.constants import CurrencyChoices, BusinessLimits
import logging

logger = logging.getLogger(__name__)


class Supplier(models.Model):
    name = models.CharField(max_length=255, verbose_name="Ta'minotchi Nomi")
    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefon Raqami")
    notes = models.TextField(blank=True, null=True, verbose_name="Izohlar")
    
    # Initial balance when supplier is created - never changes after creation
    initial_balance_uzs = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=0, 
        verbose_name="Boshlang'ich Balans UZS",
        help_text="Musbat: Siz qarzdorsiz | Manfiy: Ta'minotchi qarzdor"
    )
    initial_balance_usd = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=0, 
        verbose_name="Boshlang'ich Balans USD",  
        help_text="Musbat: Siz qarzdorsiz | Manfiy: Ta'minotchi qarzdor"
    )
    
    # Current running balance - gets updated with transactions
    balance_uzs = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=0, 
        verbose_name="Joriy Balans UZS",
        help_text="Musbat: Siz qarzdorsiz | Manfiy: Ta'minotchi qarzdor"
    )
    balance_usd = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=0, 
        verbose_name="Joriy Balans USD",
        help_text="Musbat: Siz qarzdorsiz | Manfiy: Ta'minotchi qarzdor"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        """Set initial balance equal to current balance when creating new supplier"""
        if not self.pk:  # New supplier being created
            self.initial_balance_uzs = self.balance_uzs
            self.initial_balance_usd = self.balance_usd
        super().save(*args, **kwargs)

    def add_debt(self, amount, currency):
        """Add debt when acquisition is made without payment"""
        if currency == CurrencyChoices.UZS:
            self.balance_uzs += amount
        elif currency == CurrencyChoices.USD:
            self.balance_usd += amount
        self.save(update_fields=['balance_uzs', 'balance_usd', 'updated_at'])

    def reduce_debt(self, amount, currency):
        """Reduce debt when payment is made"""
        if currency == CurrencyChoices.UZS:
            self.balance_uzs -= amount
        elif currency == CurrencyChoices.USD:
            self.balance_usd -= amount
        self.save(update_fields=['balance_uzs', 'balance_usd', 'updated_at'])

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Ta'minotchi"
        verbose_name_plural = "Ta'minotchilar"
        ordering = ['name']


class SupplierPayment(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='payments', verbose_name="Ta'minotchi")
    payment_date = models.DateTimeField(default=timezone.now, verbose_name="To'lov Sanasi")
    amount = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="Miqdor")
    currency = models.CharField(max_length=3, choices=CurrencyChoices.choices, verbose_name="Valyuta")
    paid_from_account = models.ForeignKey(
        'accounting.FinancialAccount', 
        on_delete=models.PROTECT, 
        verbose_name="To'lov Hisobi"
    )
    notes = models.TextField(blank=True, null=True, verbose_name="Izohlar")
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        """Validate payment data"""
        super().clean()
        
        if self.amount <= 0:
            raise ValidationError("To'lov miqdori musbat bo'lishi kerak.")
        
        if self.paid_from_account and self.paid_from_account.currency != self.currency:
            raise ValidationError(
                f"Hisob valyutasi ({self.paid_from_account.currency}) "
                f"to'lov valyutasi ({self.currency}) bilan mos kelmaydi."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            # Update supplier balance (reduce debt)
            self.supplier.reduce_debt(self.amount, self.currency)
            # Update financial account (reduce balance for payment)
            self.paid_from_account.current_balance -= self.amount
            self.paid_from_account.save(update_fields=['current_balance', 'updated_at'])

    def __str__(self):
        return f"{self.supplier.name} - {self.amount:,.2f} {self.currency} - {self.payment_date.strftime('%d-%m-%Y')}"

    class Meta:
        verbose_name = "Ta'minotchi To'lovi"
        verbose_name_plural = "Ta'minotchi To'lovlari"
        ordering = ['-payment_date']


class Agent(models.Model):
    name = models.CharField(max_length=255, verbose_name="Agent Nomi")
    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefon Raqami")
    notes = models.TextField(blank=True, null=True, verbose_name="Izohlar")
    
    # Initial balance when agent is created - never changes after creation
    initial_balance_uzs = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=0, 
        verbose_name="Boshlang'ich Balans UZS",
        help_text="Musbat: Agent qarzdor | Manfiy: Siz qarzdorsiz"
    )
    initial_balance_usd = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=0, 
        verbose_name="Boshlang'ich Balans USD",
        help_text="Musbat: Agent qarzdor | Manfiy: Siz qarzdorsiz"
    )
    
    # Current running balance - gets updated with transactions
    balance_uzs = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=0, 
        verbose_name="Joriy Balans UZS",
        help_text="Musbat: Agent qarzdor | Manfiy: Siz qarzdorsiz"
    )
    balance_usd = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=0, 
        verbose_name="Joriy Balans USD",
        help_text="Musbat: Agent qarzdor | Manfiy: Siz qarzdorsiz"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        """Set initial balance equal to current balance when creating new agent"""
        if not self.pk:  # New agent being created
            self.initial_balance_uzs = self.balance_uzs
            self.initial_balance_usd = self.balance_usd
        super().save(*args, **kwargs)

    def add_debt(self, amount, currency):
        """Add debt when sale is made to agent"""
        if currency == CurrencyChoices.UZS:
            self.balance_uzs += amount
        elif currency == CurrencyChoices.USD:
            self.balance_usd += amount
        self.save(update_fields=['balance_uzs', 'balance_usd', 'updated_at'])

    def reduce_debt(self, amount, currency):
        """Reduce debt when agent makes payment"""
        if currency == CurrencyChoices.UZS:
            self.balance_uzs -= amount
        elif currency == CurrencyChoices.USD:
            self.balance_usd -= amount
        self.save(update_fields=['balance_uzs', 'balance_usd', 'updated_at'])

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Agent"
        verbose_name_plural = "Agentlar"
        ordering = ['name']


class AgentPayment(models.Model):
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='payments', verbose_name="Agent")
    payment_date = models.DateTimeField(default=timezone.now, verbose_name="To'lov Sanasi")
    amount = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="Miqdor")
    currency = models.CharField(max_length=3, choices=CurrencyChoices.choices, verbose_name="Valyuta")
    paid_to_account = models.ForeignKey(
        'accounting.FinancialAccount', 
        on_delete=models.PROTECT, 
        verbose_name="To'lov Hisobi"
    )
    notes = models.TextField(blank=True, null=True, verbose_name="Izohlar")
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        """Validate payment data"""
        super().clean()
        
        if self.amount <= 0:
            raise ValidationError("To'lov miqdori musbat bo'lishi kerak.")
        
        if self.paid_to_account and self.paid_to_account.currency != self.currency:
            raise ValidationError(
                f"Hisob valyutasi ({self.paid_to_account.currency}) "
                f"to'lov valyutasi ({self.currency}) bilan mos kelmaydi."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            # Update agent balance
            self.agent.reduce_debt(self.amount, self.currency)
            # Update financial account
            self.paid_to_account.current_balance += self.amount
            self.paid_to_account.save(update_fields=['current_balance', 'updated_at'])

    def __str__(self):
        return f"{self.agent.name} - {self.amount:,.2f} {self.currency} - {self.payment_date.strftime('%d-%m-%Y')}"

    class Meta:
        verbose_name = "Agent To'lovi"
        verbose_name_plural = "Agent To'lovlari"
        ordering = ['-payment_date']