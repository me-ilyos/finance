from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.db.models.functions import Coalesce
from decimal import Decimal
from django.db import transaction
from apps.accounting.models import FinancialAccount
from apps.sales.models import Sale


class Supplier(models.Model):
    name = models.CharField(max_length=255, verbose_name="Ta'minotchi Nomi")
    contact_person = models.CharField(max_length=255, blank=True, null=True, verbose_name="Mas'ul Shaxs")
    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefon Raqami")
    email = models.EmailField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True, verbose_name="Izohlar")
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

    def get_total_sales_uzs(self):
        from apps.sales.models import Sale # Local import to avoid circular dependency
        return Sale.objects.filter(agent=self, sale_currency='UZS').aggregate(total=models.Sum('total_sale_amount'))['total'] or 0

    def get_total_sales_usd(self):
        from apps.sales.models import Sale # Local import
        return Sale.objects.filter(agent=self, sale_currency='USD').aggregate(total=models.Sum('total_sale_amount'))['total'] or 0

    def get_total_payments_uzs(self):
        return self.payments.filter(paid_to_account__currency='UZS').aggregate(total=models.Sum('amount_paid_uzs'))['total'] or 0

    def get_total_payments_usd(self):
        return self.payments.filter(paid_to_account__currency='USD').aggregate(total=models.Sum('amount_paid_usd'))['total'] or 0

    def update_balance_on_sale_creation(self, sale_amount, sale_currency):
        if sale_currency == 'UZS':
            self.outstanding_balance_uzs += sale_amount
        elif sale_currency == 'USD':
            self.outstanding_balance_usd += sale_amount
        self.save(update_fields=['outstanding_balance_uzs', 'outstanding_balance_usd', 'updated_at'])

    def update_balance_on_payment(self, amount_uzs, amount_usd):
        """
        Updates the agent's outstanding balance when a payment is made.
        `amount_uzs` and `amount_usd` should be positive values representing the payment.
        """
        self.outstanding_balance_uzs -= amount_uzs
        self.outstanding_balance_usd -= amount_usd
        self.save(update_fields=['outstanding_balance_uzs', 'outstanding_balance_usd', 'updated_at'])

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
    related_sale = models.ForeignKey(
        'sales.Sale', 
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name='agent_payments', 
        verbose_name="Bog'liq Sotuv (Qarz uchun)"
    )
    notes = models.TextField(blank=True, null=True, verbose_name="Izohlar")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_auto_created = models.BooleanField(default=False, help_text="Bu tolov sotuvdagi boshlang'ich tolovdan avtomatik yaratilganmi?")

    def clean(self):
        super().clean()
        if not self.agent:
            raise ValidationError("Agent tanlanishi shart.")

        if self.amount_paid_uzs < 0 or self.amount_paid_usd < 0:
            raise ValidationError("To'lov miqdori manfiy bo'lishi mumkin emas.")
        
        if self.amount_paid_uzs == 0 and self.amount_paid_usd == 0:
            raise ValidationError("Kamida bitta valyutada to'lov miqdori kiritilishi kerak.")

        if not self.paid_to_account:
            raise ValidationError("To'lov hisobi tanlanishi shart.")

        payment_currency = None
        if self.amount_paid_uzs > 0 and self.amount_paid_usd > 0:
            raise ValidationError("Bir vaqtda UZS va USD da to'lov qilish mumkin emas. Alohida to'lovlar yarating.")
        elif self.amount_paid_uzs > 0:
            payment_currency = 'UZS'
        elif self.amount_paid_usd > 0:
            payment_currency = 'USD'
        
        if payment_currency and self.paid_to_account.currency != payment_currency:
            raise ValidationError({
                'paid_to_account': f"To'lov hisobi valyutasi ({self.paid_to_account.currency}) to'lov valyutasiga ({payment_currency}) mos kelmadi."
            })

        if self.related_sale:
            if self.related_sale.agent != self.agent:
                raise ValidationError({
                    'related_sale': "Tanlangan sotuv bu agentga tegishli emas."
                })
            
            if self.related_sale.sale_currency != payment_currency:
                raise ValidationError({
                    'related_sale': f"Sotuv valyutasi ({self.related_sale.sale_currency}) to'lov valyutasiga ({payment_currency}) mos kelmadi. Faqat {self.related_sale.sale_currency}da to'lov qila olasiz."
                })

            # Recalculate effective balance considering this payment might be an update
            # For new payments, original_paid_on_this_sale is 0
            # For existing, it's the amount of *this* payment record as it was before this save
            original_paid_by_this_record = 0
            if self.pk: # if this is an update to an existing AgentPayment
                try:
                    db_instance = AgentPayment.objects.get(pk=self.pk)
                    if self.related_sale.sale_currency == 'UZS':
                        original_paid_by_this_record = db_instance.amount_paid_uzs
                    else:
                        original_paid_by_this_record = db_instance.amount_paid_usd
                except AgentPayment.DoesNotExist:
                    pass # Should not happen if self.pk exists
            
            # Balance on sale EXCLUDING the current payment being edited (if it's an update)
            balance_excluding_this_payment = self.related_sale.balance_due_on_this_sale + original_paid_by_this_record
            current_payment_amount = self.amount_paid_uzs if payment_currency == 'UZS' else self.amount_paid_usd

            if current_payment_amount > balance_excluding_this_payment:
                 raise ValidationError({
                    'amount_paid_uzs' if payment_currency == 'UZS' else 'amount_paid_usd': 
                    f"To'lov miqdori ({current_payment_amount:,.0f} {payment_currency}) sotuv qoldig'idan ({balance_excluding_this_payment:,.0f} {payment_currency}) oshmasligi kerak."
                })

    def save(self, *args, **kwargs):
        # self.full_clean() # Not calling full_clean here to avoid issues with admin/forms calling it multiple times
        # It's better to rely on form validation and direct calls to clean() if needed.
        
        with transaction.atomic():
            # Determine payment currency and amount based on which field is populated
            payment_amount = 0
            payment_currency = self.paid_to_account.currency # Assume account currency is the payment currency

            if payment_currency == 'UZS' and self.amount_paid_uzs > 0:
                payment_amount = self.amount_paid_uzs
            elif payment_currency == 'USD' and self.amount_paid_usd > 0:
                payment_amount = self.amount_paid_usd
            elif self.amount_paid_uzs > 0: # Fallback if account currency was somehow not UZS
                payment_currency = 'UZS'
                payment_amount = self.amount_paid_uzs
            elif self.amount_paid_usd > 0: # Fallback if account currency was somehow not USD
                payment_currency = 'USD'
                payment_amount = self.amount_paid_usd
            
            # Handle previous state for updates
            original_payment_amount_in_account_currency = 0
            original_related_sale_id = None
            original_paid_to_account_id = None

            if self.pk: # If this is an update
                try:
                    db_instance = AgentPayment.objects.select_related('paid_to_account', 'related_sale').get(pk=self.pk)
                    original_paid_to_account_id = db_instance.paid_to_account_id
                    if db_instance.paid_to_account.currency == 'UZS':
                        original_payment_amount_in_account_currency = db_instance.amount_paid_uzs
                    else:
                        original_payment_amount_in_account_currency = db_instance.amount_paid_usd
                    original_related_sale_id = db_instance.related_sale_id
                except AgentPayment.DoesNotExist:
                    pass # Should not happen

            # 1. Update Financial Account
            account = self.paid_to_account
            if self.pk and original_paid_to_account_id == account.id: # Payment account unchanged
                # Adjust for the difference
                account.current_balance += (payment_amount - original_payment_amount_in_account_currency)
            elif self.pk and original_paid_to_account_id != account.id: # Payment account changed
                # Revert from old account
                if original_paid_to_account_id:
                    old_account = FinancialAccount.objects.get(pk=original_paid_to_account_id)
                    old_account.current_balance -= original_payment_amount_in_account_currency
                    old_account.save(update_fields=['current_balance', 'updated_at'])
                # Add to new account
                account.current_balance += payment_amount
            else: # New payment
                account.current_balance += payment_amount
            account.save(update_fields=['current_balance', 'updated_at'])

            # 2. Update Agent's Outstanding Balance
            agent_to_update = self.agent
            amount_paid_uzs_diff = self.amount_paid_uzs
            amount_paid_usd_diff = self.amount_paid_usd

            if self.pk: # if updating, calculate the actual change in payment amounts
                db_instance = AgentPayment.objects.get(pk=self.pk) # Re-fetch to be safe
                amount_paid_uzs_diff = self.amount_paid_uzs - db_instance.amount_paid_uzs
                amount_paid_usd_diff = self.amount_paid_usd - db_instance.amount_paid_usd
            
            agent_to_update.outstanding_balance_uzs -= amount_paid_uzs_diff
            agent_to_update.outstanding_balance_usd -= amount_paid_usd_diff
            agent_to_update.save(update_fields=['outstanding_balance_uzs', 'outstanding_balance_usd', 'updated_at'])

            super().save(*args, **kwargs) # Save the AgentPayment itself first

            # 3. Update Related Sale's paid_amount_on_this_sale
            # If related_sale was changed, revert from old sale and apply to new one
            if self.pk and original_related_sale_id and original_related_sale_id != self.related_sale_id:
                from apps.sales.models import Sale as SaleModel # Local import
                try:
                    old_sale = SaleModel.objects.get(pk=original_related_sale_id)
                    if payment_currency == 'UZS': # Use currency of the original payment for reverting
                        old_sale.paid_amount_on_this_sale -= original_payment_amount_in_account_currency 
                    else:
                        old_sale.paid_amount_on_this_sale -= original_payment_amount_in_account_currency
                    old_sale.save(update_fields=['paid_amount_on_this_sale', 'updated_at'])
                except SaleModel.DoesNotExist:
                    pass # Old sale might have been deleted

            if self.related_sale:
                from apps.sales.models import Sale as SaleModel # Local import
                sale_to_update = SaleModel.objects.get(pk=self.related_sale.id)
                
                # Amount of this payment in the sale's currency
                amount_for_sale_currency = 0
                if sale_to_update.sale_currency == 'UZS' and payment_currency == 'UZS':
                    amount_for_sale_currency = self.amount_paid_uzs
                elif sale_to_update.sale_currency == 'USD' and payment_currency == 'USD':
                    amount_for_sale_currency = self.amount_paid_usd
                
                current_paid_on_this_sale_by_this_record = amount_for_sale_currency
                
                # If updating, we need to find what this specific AgentPayment record contributed before
                paid_by_this_record_before_update = 0
                if self.pk and (not original_related_sale_id or original_related_sale_id == self.related_sale_id):
                    # If sale was not changed or was None before, calculate based on previous amounts of this payment
                    db_instance = AgentPayment.objects.get(pk=self.pk) # Re-fetch for safety
                    if sale_to_update.sale_currency == 'UZS':
                        paid_by_this_record_before_update = db_instance.amount_paid_uzs
                    else:
                        paid_by_this_record_before_update = db_instance.amount_paid_usd
                
                # The change this save operation makes to the sale's paid amount
                change_for_sale = current_paid_on_this_sale_by_this_record - paid_by_this_record_before_update
                sale_to_update.paid_amount_on_this_sale += change_for_sale
                
                # Ensure paid_amount_on_this_sale does not exceed total_sale_amount or go below zero
                sale_to_update.paid_amount_on_this_sale = max(0, min(sale_to_update.paid_amount_on_this_sale, sale_to_update.total_sale_amount))
                sale_to_update.save(update_fields=['paid_amount_on_this_sale', 'updated_at'])

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
