from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.db.models.functions import Coalesce
from decimal import Decimal
from django.db import transaction
from apps.accounting.models import FinancialAccount
from apps.sales.models import Sale

# Create your models here.

class Supplier(models.Model):
    name = models.CharField(max_length=255, unique=True)
    phone_number = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Agent(models.Model):
    name = models.CharField(max_length=255, unique=True)
    phone_number = models.CharField(max_length=50, blank=True, null=True)
    outstanding_balance_uzs = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    outstanding_balance_usd = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def get_total_payments_uzs(self):
        return self.agent_payments.aggregate(total_paid_uzs=Sum('amount_paid_uzs'))['total_paid_uzs'] or Decimal('0.00')

    def get_total_payments_usd(self):
        return self.agent_payments.aggregate(total_paid_usd=Sum('amount_paid_usd'))['total_paid_usd'] or Decimal('0.00')

    def update_balance_on_payment(self, amount_paid_uzs=None, amount_paid_usd=None):
        if amount_paid_uzs and amount_paid_uzs > 0:
            self.outstanding_balance_uzs = (self.outstanding_balance_uzs or Decimal('0.00')) - amount_paid_uzs
        if amount_paid_usd and amount_paid_usd > 0:
            self.outstanding_balance_usd = (self.outstanding_balance_usd or Decimal('0.00')) - amount_paid_usd
        self.save()

class AgentPayment(models.Model):
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='agent_payments')
    payment_date = models.DateTimeField(default=timezone.now)
    
    related_sale = models.ForeignKey(
        Sale, 
        on_delete=models.SET_NULL,
        null=True, 
        blank=True, 
        related_name='payments_for_this_sale',
        help_text="Optionally link this payment to a specific sale by this agent."
    )
    
    amount_paid_uzs = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, default=Decimal('0.00'))
    amount_paid_usd = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, default=Decimal('0.00'))
    
    paid_to_account = models.ForeignKey(
        FinancialAccount, 
        on_delete=models.PROTECT,
        related_name='agent_payments_received'
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if not self.amount_paid_uzs and not self.amount_paid_usd:
            raise ValidationError("At least one payment amount (UZS or USD) must be provided.")
        if self.amount_paid_uzs and self.amount_paid_uzs < 0:
            raise ValidationError({'amount_paid_uzs': "UZS payment amount cannot be negative."})
        if self.amount_paid_usd and self.amount_paid_usd < 0:
            raise ValidationError({'amount_paid_usd': "USD payment amount cannot be negative."})

        if self.paid_to_account:
            payment_currency = None
            payment_amount = Decimal('0.00')
            if self.amount_paid_uzs and self.amount_paid_uzs > 0:
                payment_currency = 'UZS'
                payment_amount = self.amount_paid_uzs
            elif self.amount_paid_usd and self.amount_paid_usd > 0:
                payment_currency = 'USD'
                payment_amount = self.amount_paid_usd

            if payment_currency and self.paid_to_account.currency != payment_currency:
                raise ValidationError({
                    'paid_to_account': f"Account currency ({self.paid_to_account.currency}) must match payment currency ({payment_currency})."
                })
            if self.amount_paid_uzs and self.amount_paid_uzs > 0 and self.amount_paid_usd and self.amount_paid_usd > 0:
                 raise ValidationError("Cannot process UZS and USD payment to a single account in one transaction. Please create separate payments.")

        if self.related_sale:
            if self.related_sale.agent_id != self.agent_id:
                raise ValidationError({'related_sale': "This sale does not belong to the selected agent."})
            
            sale_currency = self.related_sale.sale_currency
            amount_to_pay_for_sale = self.amount_paid_uzs if sale_currency == 'UZS' else self.amount_paid_usd

            if (sale_currency == 'UZS' and (self.amount_paid_usd and self.amount_paid_usd > 0)) or \
               (sale_currency == 'USD' and (self.amount_paid_uzs and self.amount_paid_uzs > 0)):
                raise ValidationError({
                    'amount_paid_uzs': f"Payment currency must match the selected sale's currency ({sale_currency}). Only provide amount in {sale_currency}.",
                    'amount_paid_usd': f"Payment currency must match the selected sale's currency ({sale_currency}). Only provide amount in {sale_currency}."
                })

            if amount_to_pay_for_sale is None or amount_to_pay_for_sale <= 0:
                 raise ValidationError(f"Payment amount for the selected sale (in {sale_currency}) must be greater than zero.")

            if amount_to_pay_for_sale > self.related_sale.balance_due_on_this_sale:
                raise ValidationError(
                    f"Payment amount ({amount_to_pay_for_sale} {sale_currency}) exceeds the balance due ({self.related_sale.balance_due_on_this_sale} {sale_currency}) for the selected sale."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        
        with transaction.atomic():
            # Update financial account balance
            if self.paid_to_account:
                account = FinancialAccount.objects.select_for_update().get(pk=self.paid_to_account.pk)
                if self.amount_paid_uzs and self.amount_paid_uzs > 0:
                    if account.currency != 'UZS':
                         raise ValidationError("Programming error: Account currency mismatch for UZS payment during save.")
                    account.current_balance += self.amount_paid_uzs
                elif self.amount_paid_usd and self.amount_paid_usd > 0:
                    if account.currency != 'USD':
                        raise ValidationError("Programming error: Account currency mismatch for USD payment during save.")
                    account.current_balance += self.amount_paid_usd
                account.save()

            # If payment is linked to a specific sale, update that sale's paid_amount
            if self.related_sale:
                with transaction.atomic(): # Ensure sale update is atomic with payment save
                    sale_to_update = Sale.objects.select_for_update().get(pk=self.related_sale.pk)
                    if self.amount_paid_uzs and self.amount_paid_uzs > 0 and sale_to_update.sale_currency == 'UZS':
                        sale_to_update.paid_amount_on_this_sale += self.amount_paid_uzs
                    elif self.amount_paid_usd and self.amount_paid_usd > 0 and sale_to_update.sale_currency == 'USD':
                        sale_to_update.paid_amount_on_this_sale += self.amount_paid_usd
                    else:
                        # This case should ideally be caught by clean() method
                        raise ValidationError("Payment currency does not match related sale currency or amount is zero/negative.")
                    sale_to_update.save()

            # Agent's total outstanding balance is updated in the view after this payment is successfully saved.
            super().save(*args, **kwargs)

    def __str__(self):
        payment_str = []
        if self.amount_paid_uzs and self.amount_paid_uzs > 0:
            payment_str.append(f"{self.amount_paid_uzs} UZS")
        if self.amount_paid_usd and self.amount_paid_usd > 0:
            payment_str.append(f"{self.amount_paid_usd} USD")
        
        return f"Payment from {self.agent.name} of {', '.join(payment_str)} to {self.paid_to_account.name} on {self.payment_date.strftime('%Y-%m-%d')}"
