from django import template
from decimal import Decimal

register = template.Library()


@register.filter
def positive_balance_count(accounts):
    """Count accounts with positive balance"""
    return sum(1 for account in accounts if account.current_balance >= 0)


@register.filter
def balance_class(balance):
    """Get CSS class for balance display"""
    if not balance:
        return 'balance-zero'
    
    balance = Decimal(str(balance))
    if balance > 0:
        return 'balance-positive'
    elif balance < 0:
        return 'balance-negative'
    else:
        return 'balance-zero'


@register.filter
def format_currency(amount, currency=''):
    """Format currency amount for display"""
    if not amount:
        return "0.00"
    
    try:
        amount = Decimal(str(amount))
        if currency == 'UZS':
            return f"{amount:,.0f}"
        else:
            return f"{amount:,.2f}"
    except (ValueError, TypeError):
        return "0.00"


@register.filter
def account_icon_class(account_type):
    """Get appropriate icon class for account type"""
    icon_map = {
        'BANK_UZS': 'fas fa-university',
        'BANK_USD': 'fas fa-university',
        'CASH_UZS': 'fas fa-money-bill-wave',
        'CASH_USD': 'fas fa-money-bill-wave',
        'CARD_UZS': 'fas fa-credit-card',
        'CARD_USD': 'fas fa-credit-card',
    }
    return icon_map.get(account_type, 'fas fa-wallet')


@register.filter
def transaction_amount_class(balance_effect):
    """Get CSS class for transaction amount based on effect"""
    return 'amount-income' if balance_effect == 'income' else 'amount-expense'


@register.filter
def currency_count(accounts):
    """Count unique currencies in accounts"""
    currencies = set(account.currency for account in accounts)
    return len(currencies) 