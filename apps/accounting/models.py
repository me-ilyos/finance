from django.db import models

# Create your models here.

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
        return f"{self.name} ({self.get_account_type_display()} - {self.get_currency_display()})"
