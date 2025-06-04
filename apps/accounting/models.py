from django.db import models
from django.utils import timezone
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from apps.core.constants import CurrencyChoices, AccountTypeChoices
import logging

logger = logging.getLogger(__name__)


class FinancialAccount(models.Model):
    name = models.CharField(max_length=255, unique=True)
    account_type = models.CharField(max_length=20, choices=AccountTypeChoices.choices)
    currency = models.CharField(max_length=3, choices=CurrencyChoices.choices)
    current_balance = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=0.00,
        help_text="Hisobning joriy balansi"
    )
    account_details = models.TextField(blank=True, null=True, help_text="E.g., last 4 digits of card, bank account number")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def has_sufficient_balance(self, amount):
        """Check if account has sufficient balance for the given amount"""
        return self.current_balance >= amount

    def formatted_balance(self):
        """Return formatted balance with currency"""
        return f"{self.current_balance:,.2f} {self.currency}"

    def __str__(self):
        return f"{self.name} ({self.get_account_type_display()} - {self.currency}) - Balance: {self.current_balance}"

    class Meta:
        verbose_name = "Financial Account"
        verbose_name_plural = "Financial Accounts"


class Expenditure(models.Model):
    class ExpenditureType(models.TextChoices):
        GENERAL = 'GENERAL', 'General Expense'
        SUPPLIER_PAYMENT = 'SUPPLIER_PAYMENT', 'Supplier Payment'
    
    expenditure_type = models.CharField(
        max_length=20, 
        choices=ExpenditureType.choices, 
        default=ExpenditureType.GENERAL,
        verbose_name="Xarajat Turi"
    )
    expenditure_date = models.DateTimeField(default=timezone.now)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CurrencyChoices.choices)

    paid_from_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name='expenditures_paid'
    )
    
    # For supplier payments
    supplier = models.ForeignKey(
        'contacts.Supplier',
        on_delete=models.PROTECT,
        related_name='payments_received',
        blank=True,
        null=True,
        verbose_name="Ta'minotchi",
        help_text="Ta'minotchiga to'lov qilish uchun tanlang"
    )
    
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """Validate expenditure data including currency match and balance"""
        super().clean()
        
        # Validate expenditure type and supplier relationship
        if self.expenditure_type == self.ExpenditureType.SUPPLIER_PAYMENT and not self.supplier:
            raise ValidationError({
                'supplier': "Ta'minotchiga to'lov qilish uchun ta'minotchi tanlanishi kerak."
            })
        
        if self.supplier and self.expenditure_type != self.ExpenditureType.SUPPLIER_PAYMENT:
            raise ValidationError({
                'expenditure_type': "Ta'minotchi tanlangan bo'lsa, xarajat turi 'Ta'minotchiga to'lov' bo'lishi kerak."
            })
        
        if self.paid_from_account and self.currency != self.paid_from_account.currency:
            raise ValidationError({
                'paid_from_account': f"Currency mismatch: account uses {self.paid_from_account.currency}, "
                                   f"expenditure uses {self.currency}."
            })
        
        if self.amount is not None and self.amount <= 0:
            raise ValidationError({
                'amount': "Expenditure amount must be positive."
            })
        
        # Validate sufficient balance
        if self.amount and self.paid_from_account:
            available_balance = self.paid_from_account.current_balance
            
            # For updates, add back the original amount to available balance
            if self.pk:
                try:
                    original = Expenditure.objects.get(pk=self.pk)
                    if original.paid_from_account_id == self.paid_from_account_id:
                        available_balance += original.amount
                except Expenditure.DoesNotExist:
                    pass
            
            if available_balance < self.amount:
                raise ValidationError({
                    'amount': f"Insufficient balance. Available: {available_balance:,.2f} {self.currency}"
                })

    def save(self, *args, **kwargs):
        """Save expenditure and update related records"""
        self.full_clean()
        is_new = self.pk is None
        
        # Get original expenditure for updates
        original_expenditure = None
        if not is_new:
            try:
                original_expenditure = Expenditure.objects.get(pk=self.pk)
            except Expenditure.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
        
        # Update related records
        if is_new:
            self._update_related_records_new()
        else:
            self._update_related_records_update(original_expenditure)

    def _update_related_records_new(self):
        """Update related records for new expenditure"""
        try:
            with transaction.atomic():
                # Update financial account balance
                self.paid_from_account.current_balance -= self.amount
                self.paid_from_account.save(update_fields=['current_balance', 'updated_at'])
                
                # Update supplier balance if this is a supplier payment
                if self.expenditure_type == self.ExpenditureType.SUPPLIER_PAYMENT and self.supplier:
                    if self.currency == CurrencyChoices.UZS:
                        self.supplier.balance_uzs -= self.amount
                    elif self.currency == CurrencyChoices.USD:
                        self.supplier.balance_usd -= self.amount
                    
                    self.supplier.save(update_fields=['balance_uzs', 'balance_usd', 'updated_at'])
                    logger.info(f"Updated supplier {self.supplier.id} balance for payment {self.id}")
                
        except Exception as e:
            logger.error(f"Error updating related records for expenditure {self.pk}: {e}")
            raise

    def _update_related_records_update(self, original_expenditure):
        """Update related records for expenditure update"""
        if not original_expenditure:
            return
            
        try:
            with transaction.atomic():
                # Calculate differences
                amount_diff = self.amount - original_expenditure.amount
                
                # Update financial account
                if self.paid_from_account_id == original_expenditure.paid_from_account_id:
                    # Same account, adjust difference
                    self.paid_from_account.current_balance -= amount_diff
                else:
                    # Account changed, revert from old and deduct from new
                    original_account = FinancialAccount.objects.get(pk=original_expenditure.paid_from_account_id)
                    original_account.current_balance += original_expenditure.amount
                    original_account.save(update_fields=['current_balance', 'updated_at'])
                    
                    self.paid_from_account.current_balance -= self.amount
                
                self.paid_from_account.save(update_fields=['current_balance', 'updated_at'])
                
                # Update supplier balances if needed
                self._update_supplier_balance_on_change(original_expenditure)
                
        except Exception as e:
            logger.error(f"Error updating related records for expenditure update {self.pk}: {e}")
            raise

    def _update_supplier_balance_on_change(self, original_expenditure):
        """Update supplier balances when expenditure changes"""
        # Revert original supplier payment
        if (original_expenditure.expenditure_type == self.ExpenditureType.SUPPLIER_PAYMENT and 
            original_expenditure.supplier):
            
            supplier = original_expenditure.supplier
            if original_expenditure.currency == CurrencyChoices.UZS:
                supplier.balance_uzs += original_expenditure.amount
            elif original_expenditure.currency == CurrencyChoices.USD:
                supplier.balance_usd += original_expenditure.amount
            supplier.save(update_fields=['balance_uzs', 'balance_usd', 'updated_at'])
        
        # Apply new supplier payment
        if (self.expenditure_type == self.ExpenditureType.SUPPLIER_PAYMENT and self.supplier):
            if self.currency == CurrencyChoices.UZS:
                self.supplier.balance_uzs -= self.amount
            elif self.currency == CurrencyChoices.USD:
                self.supplier.balance_usd -= self.amount
            self.supplier.save(update_fields=['balance_uzs', 'balance_usd', 'updated_at'])

    @property
    def is_supplier_payment(self):
        """Check if this expenditure is a supplier payment"""
        return self.expenditure_type == self.ExpenditureType.SUPPLIER_PAYMENT

    def __str__(self):
        if self.is_supplier_payment and self.supplier:
            return f"Payment to {self.supplier.name} - {self.amount} {self.currency} on {self.expenditure_date.strftime('%Y-%m-%d')}"
        return f"{self.description} - {self.amount} {self.currency} on {self.expenditure_date.strftime('%Y-%m-%d')}"

    class Meta:
        verbose_name = "Expenditure"
        verbose_name_plural = "Expenditures"
        ordering = ['-expenditure_date']
