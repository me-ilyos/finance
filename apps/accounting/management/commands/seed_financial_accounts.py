from django.core.management.base import BaseCommand
from apps.accounting.models import FinancialAccount
from apps.core.constants import AccountTypeChoices, CurrencyChoices


class Command(BaseCommand):
    help = "Create initial financial accounts with zero balance (idempotent)."

    def handle(self, *args, **options):
        accounts_to_create = [
            # Name, AccountType, Currency
            ("МУСЛИМБЕК КАРТА СУМ", AccountTypeChoices.CARD_UZS, CurrencyChoices.UZS),
            ("МУСЛИМБЕК КАРТА USD ДОЛЛАР", AccountTypeChoices.CARD_USD, CurrencyChoices.USD),
            ("НОДИРБЕК КАРТА USD ДОЛЛАР", AccountTypeChoices.CARD_USD, CurrencyChoices.USD),
            ("ШОХРУХ КАРТА USD ДОЛЛАР", AccountTypeChoices.CARD_USD, CurrencyChoices.USD),
            ("ХАСАНБОЙ КАРТА USD ДОЛЛАР", AccountTypeChoices.CARD_USD, CurrencyChoices.USD),
            ("КАПИТАЛБАНК ХИСОБ РАКАМ СУМ", AccountTypeChoices.BANK_UZS, CurrencyChoices.UZS),
            ("ТРАСТБАНК ХИСОБ РАКАМ СУМ", AccountTypeChoices.BANK_UZS, CurrencyChoices.UZS),
            ("НОДИРБЕК КАРТА СУМ", AccountTypeChoices.CARD_UZS, CurrencyChoices.UZS),
            ("ШОХРУХ КАРТА СУМ", AccountTypeChoices.CARD_UZS, CurrencyChoices.UZS),
            ("ХАСАНБОЙ КАРТА СУМ", AccountTypeChoices.CARD_UZS, CurrencyChoices.UZS),
            ("КАССА USD ДОЛЛАР", AccountTypeChoices.CASH_USD, CurrencyChoices.USD),
            ("КАССА СУМ", AccountTypeChoices.CASH_UZS, CurrencyChoices.UZS),
        ]

        created_count = 0
        updated_count = 0

        for name, acc_type, currency in accounts_to_create:
            account, created = FinancialAccount.objects.get_or_create(
                name=name,
                defaults={
                    'account_type': acc_type,
                    'currency': currency,
                    'current_balance': 0,
                    'is_active': True,
                }
            )

            if created:
                created_count += 1
            else:
                # Ensure type/currency are aligned, but do not change existing balances
                changed = False
                if account.account_type != acc_type:
                    account.account_type = acc_type
                    changed = True
                if account.currency != currency:
                    account.currency = currency
                    changed = True
                if changed:
                    account.save(update_fields=['account_type', 'currency', 'updated_at'])
                    updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Accounts processed. Created: {created_count}, Updated: {updated_count}"
        ))


