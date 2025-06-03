from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.db import transaction
from apps.core.constants import CurrencyChoices, BusinessLimits
import logging

logger = logging.getLogger(__name__)


class SupplierManager(models.Manager):
    def get_supplier_stats(self, supplier):
        """Get supplier statistics including acquisitions and payments totals"""
        from django.apps import apps
        from django.db.models import Sum
        
        Acquisition = apps.get_model('inventory', 'Acquisition')
        Expenditure = apps.get_model('accounting', 'Expenditure')
        
        return {
            'total_acquisitions_uzs': Acquisition.objects.filter(
                supplier=supplier, transaction_currency=CurrencyChoices.UZS
            ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00'),
            
            'total_acquisitions_usd': Acquisition.objects.filter(
                supplier=supplier, transaction_currency=CurrencyChoices.USD
            ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00'),
            
            'total_payments_uzs': supplier.payments_received.filter(
                currency=CurrencyChoices.UZS,
                expenditure_type=Expenditure.ExpenditureType.SUPPLIER_PAYMENT
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
            
            'total_payments_usd': supplier.payments_received.filter(
                currency=CurrencyChoices.USD,
                expenditure_type=Expenditure.ExpenditureType.SUPPLIER_PAYMENT
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
        }


class Supplier(models.Model):
    name = models.CharField(max_length=255, verbose_name="Ta'minotchi Nomi")
    contact_person = models.CharField(max_length=255, blank=True, null=True, verbose_name="Mas'ul Shaxs")
    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefon Raqami")
    email = models.EmailField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True, verbose_name="Izohlar")
    
    # Balance fields - positive means you owe the supplier, negative means they owe you
    current_balance_uzs = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=0, 
        verbose_name="Joriy Balans UZS",
        help_text="Musbat: Siz ta'minotchiga qarzdorsiz | Manfiy: Ta'minotchi sizga qarzdor"
    )
    current_balance_usd = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=0, 
        verbose_name="Joriy Balans USD",
        help_text="Musbat: Siz ta'minotchiga qarzdorsiz | Manfiy: Ta'minotchi sizga qarzdor"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = SupplierManager()

    def update_balance_on_acquisition(self, acquisition_amount, acquisition_currency):
        """Update supplier balance when acquisition is made (increases debt to supplier)"""
        if acquisition_currency == CurrencyChoices.UZS:
            self.current_balance_uzs += acquisition_amount
        elif acquisition_currency == CurrencyChoices.USD:
            self.current_balance_usd += acquisition_amount
        self.save(update_fields=['current_balance_uzs', 'current_balance_usd', 'updated_at'])
        logger.info(f"Updated supplier {self.id} balance for acquisition: {acquisition_amount} {acquisition_currency}")

    def get_total_debt(self):
        """Get total debt owed to supplier in both currencies"""
        return {
            'uzs': max(self.current_balance_uzs, Decimal('0.00')),
            'usd': max(self.current_balance_usd, Decimal('0.00'))
        }

    def has_debt(self):
        """Check if we owe money to this supplier"""
        return self.current_balance_uzs > 0 or self.current_balance_usd > 0

    @property
    def abs_balance_uzs(self):
        """Get absolute value of UZS balance"""
        return abs(self.current_balance_uzs)

    @property
    def abs_balance_usd(self):
        """Get absolute value of USD balance"""
        return abs(self.current_balance_usd)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Ta'minotchi"
        verbose_name_plural = "Ta'minotchilar"
        ordering = ['name']


class AgentManager(models.Manager):
    def get_agent_stats(self, agent):
        """Get agent statistics including sales and payments totals"""
        from django.apps import apps
        from django.db.models import Sum
        
        Sale = apps.get_model('sales', 'Sale')
        
        return {
            'total_sales_uzs': Sale.objects.filter(
                agent=agent, sale_currency=CurrencyChoices.UZS
            ).aggregate(total=Sum('total_sale_amount'))['total'] or Decimal('0.00'),
            
            'total_sales_usd': Sale.objects.filter(
                agent=agent, sale_currency=CurrencyChoices.USD
            ).aggregate(total=Sum('total_sale_amount'))['total'] or Decimal('0.00'),
            
            'total_payments_uzs': agent.payments.aggregate(
                total=Sum('amount_paid_uzs')
            )['total'] or Decimal('0.00'),
            
            'total_payments_usd': agent.payments.aggregate(
                total=Sum('amount_paid_usd')
            )['total'] or Decimal('0.00'),
        }


class Agent(models.Model):
    name = models.CharField(max_length=255, verbose_name="Agent Nomi")
    contact_person = models.CharField(max_length=255, blank=True, null=True, verbose_name="Mas'ul Shaxs")
    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefon Raqami")
    email = models.EmailField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True, verbose_name="Izohlar")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    outstanding_balance_uzs = models.DecimalField(max_digits=20, decimal_places=2, default=0, verbose_name="Qarz UZS")
    outstanding_balance_usd = models.DecimalField(max_digits=20, decimal_places=2, default=0, verbose_name="Qarz USD")

    objects = AgentManager()

    def update_balance_on_sale(self, sale_amount, sale_currency):
        """Update agent balance when sale is created"""
        if sale_currency == CurrencyChoices.UZS:
            self.outstanding_balance_uzs += sale_amount
        elif sale_currency == CurrencyChoices.USD:
            self.outstanding_balance_usd += sale_amount
        self.save(update_fields=['outstanding_balance_uzs', 'outstanding_balance_usd', 'updated_at'])

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Agent"
        verbose_name_plural = "Agentlar"
        ordering = ['name']


class AgentPayment(models.Model):
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='payments', verbose_name="Agent")
    payment_date = models.DateTimeField(default=timezone.now, verbose_name="To'lov Sanasi")
    
    amount_paid_uzs = models.DecimalField(max_digits=20, decimal_places=2, default=0, verbose_name="To'langan Miqdor (UZS)")
    amount_paid_usd = models.DecimalField(max_digits=20, decimal_places=2, default=0, verbose_name="To'langan Miqdor (USD)")
    
    paid_to_account = models.ForeignKey(
        'accounting.FinancialAccount', 
        on_delete=models.PROTECT, 
        verbose_name="To'lov Hisobi",
        limit_choices_to={'is_active': True}
    )
    notes = models.TextField(blank=True, null=True, verbose_name="Izohlar")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_auto_created = models.BooleanField(default=False, help_text="Bu tolov sotuvdagi boshlang'ich tolovdan avtomatik yaratilganmi?")

    @property
    def payment_currency(self):
        """Get the currency of this payment"""
        if self.amount_paid_uzs > 0:
            return CurrencyChoices.UZS
        elif self.amount_paid_usd > 0:
            return CurrencyChoices.USD
        return None

    @property
    def payment_amount(self):
        """Get the amount of this payment"""
        if self.amount_paid_uzs > 0:
            return self.amount_paid_uzs
        elif self.amount_paid_usd > 0:
            return self.amount_paid_usd
        return Decimal('0.00')

    def clean(self):
        """Validate agent payment data"""
        super().clean()
        
        # Validate payment amounts
        if self.amount_paid_uzs < 0 or self.amount_paid_usd < 0:
            raise ValidationError("Payment amount cannot be negative.")

        if self.amount_paid_uzs == 0 and self.amount_paid_usd == 0:
            raise ValidationError("Payment amount must be greater than zero.")

        if self.amount_paid_uzs > 0 and self.amount_paid_usd > 0:
            raise ValidationError("Payment must be in exactly one currency (UZS or USD).")

        # Validate business limits
        if self.amount_paid_uzs > BusinessLimits.MAX_BALANCE_VALUE:
            raise ValidationError(f"UZS payment amount cannot exceed {BusinessLimits.MAX_BALANCE_VALUE}")
        if self.amount_paid_usd > BusinessLimits.MAX_BALANCE_VALUE:
            raise ValidationError(f"USD payment amount cannot exceed {BusinessLimits.MAX_BALANCE_VALUE}")

        # Validate currency match with account
        if self.paid_to_account:
            payment_currency = self.payment_currency
            if self.paid_to_account.currency != payment_currency:
                raise ValidationError(
                    f"Currency mismatch: account uses {self.paid_to_account.currency}, "
                    f"payment uses {payment_currency}."
                )

    def save(self, *args, **kwargs):
        """Save agent payment with validation"""
        self.full_clean()
        is_new = self.pk is None
        
        super().save(*args, **kwargs)
        
        # Simple post-save processing
        if is_new:
            self._update_related_records()

    def _update_related_records(self):
        """Update financial account and agent balance"""
        try:
            with transaction.atomic():
                # Update financial account
                self.paid_to_account.current_balance += self.payment_amount
                self.paid_to_account.save(update_fields=['current_balance', 'updated_at'])
                
                # Update agent balance
                self.agent.outstanding_balance_uzs -= self.amount_paid_uzs
                self.agent.outstanding_balance_usd -= self.amount_paid_usd
                self.agent.save(update_fields=['outstanding_balance_uzs', 'outstanding_balance_usd', 'updated_at'])
                
        except Exception as e:
            logger.error(f"Error updating related records for payment {self.pk}: {e}")
            raise

    def __str__(self):
        payment_details = []
        if self.amount_paid_uzs > 0:
            payment_details.append(f"{self.amount_paid_uzs:,.0f} UZS")
        if self.amount_paid_usd > 0:
            payment_details.append(f"{self.amount_paid_usd:,.2f} USD")
        payment_str = " va ".join(payment_details)
        
        return f"Agent: {self.agent.name} - {payment_str} - {self.payment_date.strftime('%d-%m-%Y')}"

    class Meta:
        verbose_name = "Agent To'lovi"
        verbose_name_plural = "Agent To'lovlari"
        ordering = ['-payment_date', '-created_at']
