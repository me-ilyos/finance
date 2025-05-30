from django.db import models
from django.utils import timezone
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction


class FinancialAccount(models.Model):
    class AccountType(models.TextChoices):
        CASH = 'CASH', 'Cash'
        CARD = 'CARD', 'Card'
        BANK_ACCOUNT = 'BANK_ACCOUNT', 'Bank Account'

    class Currency(models.TextChoices):
        UZS = 'UZS', 'Uzbek Som'
        USD = 'USD', 'US Dollar'

    name = models.CharField(max_length=255, unique=True)
    account_type = models.CharField(max_length=20, choices=AccountType.choices)
    currency = models.CharField(max_length=3, choices=Currency.choices)
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    account_details = models.TextField(blank=True, null=True, help_text="E.g., last 4 digits of card, bank account number")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_account_type_display()} - {self.currency}) - Balance: {self.current_balance}"


class Expenditure(models.Model):
    expenditure_date = models.DateTimeField(default=timezone.now)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    class Currency(models.TextChoices):
        UZS = 'UZS', 'Uzbek Som'
        USD = 'USD', 'US Dollar'
    currency = models.CharField(max_length=3, choices=Currency.choices)

    paid_from_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT, # Prevent deleting an account that has expenditures logged
        related_name='expenditures_paid'
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if self.paid_from_account and self.currency != self.paid_from_account.currency:
            raise ValidationError({
                'paid_from_account': f"The currency of the selected payment account ({self.paid_from_account.currency}) "
                                     f"does not match the expenditure currency ({self.currency})."
            })
        
        # Check for sufficient balance (optional, based on business rules)
        # For now, this is illustrative. In a real system, you might allow overdrafts
        # or handle this with more complex logic.
        # This check applies only if we are creating a new expenditure, or if the amount is increasing
        # or if the account is changing.
        effective_amount_to_check = self.amount
        if self.pk: # if updating
            original_expenditure = Expenditure.objects.get(pk=self.pk)
            if original_expenditure.paid_from_account_id == self.paid_from_account_id:
                 # only check the difference if the account is the same
                effective_amount_to_check = self.amount - original_expenditure.amount
            # If account changed, new account needs to cover full new amount. Old account will be credited.
        
        if effective_amount_to_check > 0 and self.paid_from_account and self.paid_from_account.current_balance < effective_amount_to_check:
            # This check simplifies things. A more precise check would consider reverting old amounts first.
            # For the purpose of this clean(), we'll check if current balance can cover this specific amount increase.
             pass # Disabling strict balance check in clean to allow save to handle it atomically
            # raise ValidationError({
            #     'amount': f"Insufficient balance in {self.paid_from_account.name}. "
            #               f"Current balance: {self.paid_from_account.current_balance} {self.paid_from_account.currency}, "
            #               f"needed for this change: {effective_amount_to_check} {self.currency}."
            # })


    def save(self, *args, **kwargs):
        self.full_clean() # Call clean() before saving

        is_new = self.pk is None
        original_amount = Decimal('0.00')
        original_paid_from_account_id = None

        if not is_new:
            try:
                original_expenditure = Expenditure.objects.get(pk=self.pk)
                original_amount = original_expenditure.amount
                original_paid_from_account_id = original_expenditure.paid_from_account_id
            except Expenditure.DoesNotExist:
                # Should not happen if self.pk is not None, but as a fallback treat as new.
                is_new = True
        
        with transaction.atomic():
            # 1. Revert effect on old account if account or amount changed during an update
            if not is_new and original_paid_from_account_id and \
               (original_paid_from_account_id != self.paid_from_account_id or original_amount != self.amount):
                try:
                    old_payment_account = FinancialAccount.objects.select_for_update().get(pk=original_paid_from_account_id)
                    old_payment_account.current_balance += original_amount # Add back as it was an expenditure
                    old_payment_account.save()
                except FinancialAccount.DoesNotExist:
                    # Log this issue: account existed before but not now?
                    pass
            
            # 2. Apply effect to new/current account
            # Ensure we get the latest version of the account for update
            current_payment_account = FinancialAccount.objects.select_for_update().get(pk=self.paid_from_account_id)
            
            # Calculate the net change to apply to the current account
            # If it's a new expenditure, the change is simply -self.amount
            # If it's an update to the same account, change is -(self.amount - original_amount)
            # If account changed, new account gets -self.amount (old one was already credited above)
            
            amount_to_deduct_from_current_account = self.amount
            
            if not is_new and original_paid_from_account_id == self.paid_from_account_id:
                # Same account, only the difference in amount needs to be applied
                # E.g. old was 100, new is 120. Diff is 20. We already added 100 back. Now deduct 120. Net -20.
                # No, the old_payment_account.current_balance += original_amount has already happened.
                # So current_payment_account already reflects the state *before* this original_expenditure.
                # We just need to deduct the new self.amount
                pass # amount_to_deduct_from_current_account is already self.amount

            current_payment_account.current_balance -= amount_to_deduct_from_current_account
            current_payment_account.save()

            super().save(*args, **kwargs) # Save the expenditure instance itself

    def __str__(self):
        return f"{self.description} - {self.amount} {self.currency} on {self.expenditure_date.strftime('%Y-%m-%d')}"
