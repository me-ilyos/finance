from django import template
from decimal import Decimal

register = template.Library()


@register.filter
def currency_display(amount, currency):
    """Format currency amount based on currency type"""
    if not amount:
        return "-"
    
    if currency == 'UZS':
        return f"{int(amount):,}".replace(',', ' ')
    elif currency == 'USD':
        return f"${amount:,.2f}".replace(',', ' ')
    else:
        return str(amount)


@register.filter
def currency_amount_in_column(sale, currency):
    """Get sale amount for specific currency column"""
    if sale.sale_currency == currency:
        return sale.total_sale_amount
    return None


@register.filter
def currency_profit_in_column(sale, currency):
    """Get sale profit for specific currency column"""
    if sale.sale_currency == currency:
        return sale.profit
    return None


@register.filter
def currency_unit_price_in_column(sale, currency):
    """Get unit price for specific currency column"""
    if sale.sale_currency == currency:
        return sale.unit_sale_price
    return None


@register.filter
def has_initial_payment(sale):
    """Check if sale has initial payment"""
    return sale.agent and sale.paid_amount_on_this_sale > 0


@register.filter
def buyer_display(sale):
    """Format buyer information for display"""
    if sale.agent:
        return f"Agent: {sale.agent.name}"
    elif sale.client_full_name:
        return sale.client_full_name
    else:
        return "Noma'lum"


@register.filter
def payment_status_display(sale):
    """Get payment status badge and info for sale"""
    if sale.paid_to_account:
        return {
            'type': 'account',
            'name': sale.paid_to_account.name,
            'badge': None
        }
    elif sale.agent:
        badge_info = {
            'type': 'agent_debt',
            'badge': 'bg-warning text-dark',
            'text': 'Agent Qarzi'
        }
        
        if sale.paid_amount_on_this_sale and sale.paid_amount_on_this_sale > 0:
            badge_info['payment_text'] = f"To'langan: {sale.paid_amount_on_this_sale|floatformat:0} {sale.sale_currency}"
        elif sale.initial_payment_amount and sale.initial_payment_amount == 0:
            badge_info['payment_text'] = "To'lov qilinmagan"
        
        return badge_info
    else:
        return {
            'type': 'unpaid',
            'badge': 'bg-danger',
            'text': 'To\'lanmagan'
        }


@register.filter
def ticket_description_short(acquisition):
    """Get short ticket description"""
    if not acquisition or not acquisition.ticket:
        return "N/A"
    return acquisition.ticket.description[:25] + "..." if len(acquisition.ticket.description) > 25 else acquisition.ticket.description


@register.filter 
def safe_intcomma(value):
    """Safe integer comma formatting"""
    if value is None:
        return "0"
    try:
        return f"{int(value):,}".replace(',', ' ')
    except (ValueError, TypeError):
        return "0"


@register.filter
def safe_floatcomma(value, places=2):
    """Safe float comma formatting"""
    if value is None:
        return "0.00"
    try:
        format_str = f"{{:,.{places}f}}"
        return format_str.format(float(value)).replace(',', ' ')
    except (ValueError, TypeError):
        return "0.00" 