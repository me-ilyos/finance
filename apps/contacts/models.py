from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.db import transaction
from apps.core.constants import CurrencyChoices
from .validators import PaymentValidator
from .services import AgentPaymentService
import logging

logger = logging.getLogger(__name__)


class Supplier(models.Model):
    name = models.CharField(max_length=255, verbose_name="Ta'minotchi Nomi")
    contact_person = models.CharField(max_length=255, blank=True, null=True, verbose_name="Mas'ul Shaxs")
    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefon Raqami")
    email = models.EmailField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True, verbose_name="Izohlar")
    
    # Balance fields for migration from Excel
    current_balance_uzs = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=0, 
        verbose_name="Joriy Balans UZS",
        help_text="Exceldan ko'chirishda joriy balansni kiriting (musbat, manfiy yoki nol bo'lishi mumkin)"
    )
    current_balance_usd = models.DecimalField(
        max_digits=20, 
        decimal_places=2, 
        default=0, 
        verbose_name="Joriy Balans USD",
        help_text="Exceldan ko'chirishda joriy balansni kiriting (musbat, manfiy yoki nol bo'lishi mumkin)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Ta'minotchi"
        verbose_name_plural = "Ta'minotchilar"
        ordering = ['name']


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
        try:
            PaymentValidator.validate_agent_payment(
                agent=self.agent,
                amount_uzs=self.amount_paid_uzs,
                amount_usd=self.amount_paid_usd,
                paid_to_account=self.paid_to_account
            )
        except ValidationError as e:
            if hasattr(e, 'message'):
                raise ValidationError({'__all__': e.message})
            raise

    def save(self, *args, **kwargs):
        """Save agent payment and trigger related updates"""
        self.full_clean()
        
        original_payment = None
        if self.pk:
            try:
                original_payment = AgentPayment.objects.select_related(
                    'paid_to_account', 'agent'
                ).get(pk=self.pk)
            except AgentPayment.DoesNotExist:
                logger.warning(f"Original AgentPayment {self.pk} not found during update")

        super().save(*args, **kwargs)

        try:
            AgentPaymentService.process_payment(self, original_payment)
        except Exception as e:
            logger.error(f"Error processing payment {self.pk}: {e}")
            raise

    def delete(self, *args, **kwargs):
        """Handle payment deletion with proper cleanup"""
        with transaction.atomic():
            reverse_payment = AgentPayment(
                agent=self.agent,
                amount_paid_uzs=-self.amount_paid_uzs,
                amount_paid_usd=-self.amount_paid_usd,
                paid_to_account=self.paid_to_account
            )
            
            try:
                AgentPaymentService.process_payment(reverse_payment, self)
                super().delete(*args, **kwargs)
                logger.info(f"Deleted payment {self.pk} and processed cleanup")
            except Exception as e:
                logger.error(f"Error deleting payment {self.pk}: {e}")
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
