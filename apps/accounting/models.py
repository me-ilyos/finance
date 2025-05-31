from django.db import models
from django.utils import timezone
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from apps.core.constants import CurrencyChoices, AccountTypeChoices


class FinancialAccountService:
    """Service class to handle financial account balance operations"""
    
    @staticmethod
    def update_balance_for_expenditure(account_id, amount, operation='deduct'):
        """Update account balance for expenditure operations"""
        with transaction.atomic():
            account = FinancialAccount.objects.select_for_update().get(pk=account_id)
            if operation == 'deduct':
                account.current_balance -= amount
            elif operation == 'add_back':
                account.current_balance += amount
            account.save()
            return account
    
    @staticmethod
    def handle_expenditure_update(expenditure, original_expenditure):
        """Handle balance updates when expenditure is modified"""
        with transaction.atomic():
            # If account changed, add back to old account
            if original_expenditure.paid_from_account_id != expenditure.paid_from_account_id:
                FinancialAccountService.update_balance_for_expenditure(
                    original_expenditure.paid_from_account_id, 
                    original_expenditure.amount, 
                    'add_back'
                )
                # Deduct from new account
                FinancialAccountService.update_balance_for_expenditure(
                    expenditure.paid_from_account_id, 
                    expenditure.amount, 
                    'deduct'
                )
            else:
                # Same account, handle amount difference
                amount_difference = expenditure.amount - original_expenditure.amount
                if amount_difference != 0:
                    operation = 'deduct' if amount_difference > 0 else 'add_back'
                    FinancialAccountService.update_balance_for_expenditure(
                        expenditure.paid_from_account_id, 
                        abs(amount_difference), 
                        operation
                    )


class FinancialAccount(models.Model):
    name = models.CharField(max_length=255, unique=True)
    account_type = models.CharField(max_length=20, choices=AccountTypeChoices.choices)
    currency = models.CharField(max_length=3, choices=CurrencyChoices.choices)
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
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
        """Save expenditure and update account balance"""
        self.full_clean()
        
        is_new = self.pk is None
        original_expenditure = None
        
        if not is_new:
            try:
                original_expenditure = Expenditure.objects.get(pk=self.pk)
            except Expenditure.DoesNotExist:
                is_new = True
        
        # Save the expenditure first
        super().save(*args, **kwargs)
        
        # Update account balances
        if is_new:
            FinancialAccountService.update_balance_for_expenditure(
                self.paid_from_account_id, 
                self.amount, 
                'deduct'
            )
        else:
            FinancialAccountService.handle_expenditure_update(self, original_expenditure)

    def __str__(self):
        return f"{self.description} - {self.amount} {self.currency} on {self.expenditure_date.strftime('%Y-%m-%d')}"

    class Meta:
        verbose_name = "Expenditure"
        verbose_name_plural = "Expenditures"
        ordering = ['-expenditure_date']
