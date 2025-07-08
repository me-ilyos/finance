from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction
from apps.core.constants import CurrencyChoices, AccountTypeChoices


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


class Transfer(models.Model):
    transfer_date = models.DateTimeField(default=timezone.now)
    from_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name='transfers_sent'
    )
    to_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name='transfers_received'
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CurrencyChoices.choices)
    
    # Currency conversion fields
    conversion_rate = models.DecimalField(
        max_digits=10, 
        decimal_places=4, 
        null=True, 
        blank=True,
        help_text="UZS per 1 USD exchange rate (only for cross-currency transfers)"
    )
    converted_amount = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Amount in receiving account's currency"
    )
    
    description = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """Validate transfer data"""
        super().clean()
        
        if self.from_account == self.to_account:
            raise ValidationError("Cannot transfer to the same account")
        
        if self.amount <= 0:
            raise ValidationError("Transfer amount must be positive")
        
        # Check sufficient balance
        if self.from_account and not self.from_account.has_sufficient_balance(self.amount):
            raise ValidationError(
                f"Insufficient balance in {self.from_account.name}. "
                f"Available: {self.from_account.current_balance:,.2f} {self.from_account.currency}"
            )
        
        # Handle currency conversion
        if self.from_account.currency != self.to_account.currency:
            if not self.conversion_rate:
                raise ValidationError("Conversion rate required for cross-currency transfers")
            if self.conversion_rate <= 0:
                raise ValidationError("Conversion rate must be positive")
            
            # Calculate converted amount
            if self.from_account.currency == 'USD' and self.to_account.currency == 'UZS':
                self.converted_amount = self.amount * self.conversion_rate
            elif self.from_account.currency == 'UZS' and self.to_account.currency == 'USD':
                self.converted_amount = self.amount / self.conversion_rate
            else:
                raise ValidationError("Only USD-UZS conversions are supported")
        else:
            # Same currency transfer
            self.converted_amount = self.amount
            self.conversion_rate = None

    def save(self, *args, **kwargs):
        """Save transfer and update account balances"""
        # Run validation first
        self.full_clean()
        
        with transaction.atomic():
            # Update account balances
            self.from_account.current_balance -= self.amount
            self.from_account.save(update_fields=['current_balance', 'updated_at'])
            
            self.to_account.current_balance += self.converted_amount
            self.to_account.save(update_fields=['current_balance', 'updated_at'])
            
            # Save the transfer record
            super().save(*args, **kwargs)

    def is_cross_currency(self):
        """Check if this is a cross-currency transfer"""
        return self.from_account.currency != self.to_account.currency

    def __str__(self):
        if self.is_cross_currency():
            return f"Transfer: {self.amount} {self.from_account.currency} -> {self.converted_amount} {self.to_account.currency} (Rate: {self.conversion_rate})"
        else:
            return f"Transfer: {self.amount} {self.currency} from {self.from_account.name} to {self.to_account.name}"

    class Meta:
        verbose_name = "Transfer"
        verbose_name_plural = "Transfers"
        ordering = ['-transfer_date']


class Expenditure(models.Model):
    expenditure_date = models.DateTimeField(default=timezone.now)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CurrencyChoices.choices)

    paid_from_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name='expenditures_paid'
    )
    
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """Validate expenditure data including currency match and balance"""
        super().clean()
        
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
        
        with transaction.atomic():
            if is_new:
                self.paid_from_account.current_balance -= self.amount
                self.paid_from_account.save(update_fields=['current_balance', 'updated_at'])
            else:
                self._update_balance_for_edit(original_expenditure)

    def _update_balance_for_edit(self, original_expenditure):
        """Update related records for expenditure update"""
        if not original_expenditure:
            return
            
        amount_diff = self.amount - original_expenditure.amount
        
        if self.paid_from_account_id == original_expenditure.paid_from_account_id:
            self.paid_from_account.current_balance -= amount_diff
        else:
            original_account = FinancialAccount.objects.get(pk=original_expenditure.paid_from_account_id)
            original_account.current_balance += original_expenditure.amount
            original_account.save(update_fields=['current_balance', 'updated_at'])
            
            self.paid_from_account.current_balance -= self.amount
        
        self.paid_from_account.save(update_fields=['current_balance', 'updated_at'])

    def __str__(self):
        return f"{self.description} - {self.amount} {self.currency} on {self.expenditure_date.strftime('%Y-%m-%d')}"

    class Meta:
        verbose_name = "Expenditure"
        verbose_name_plural = "Expenditures"
        ordering = ['-expenditure_date']
