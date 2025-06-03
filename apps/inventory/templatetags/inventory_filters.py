from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def format_currency_amount(acquisition, field_type='unit_price'):
    """
    Format currency amount based on acquisition's currency
    field_type can be 'unit_price' or 'total_amount'
    """
    if not acquisition:
        return "-"
    
    if field_type == 'unit_price':
        if acquisition.unit_price is not None:
            if acquisition.currency == 'UZS':
                return f"{acquisition.unit_price:,.0f} UZS"
            elif acquisition.currency == 'USD':
                return f"${acquisition.unit_price:,.2f}"
    elif field_type == 'total_amount':
        if acquisition.total_amount is not None:
            if acquisition.currency == 'UZS':
                return f"{acquisition.total_amount:,.0f} UZS"
            elif acquisition.currency == 'USD':
                return f"${acquisition.total_amount:,.2f}"
    
    return "-"


@register.filter
def format_quantity_display(acquisition):
    """Format available/initial quantity display"""
    if not acquisition:
        return "-"
    
    available = f"{acquisition.available_quantity:,}"
    initial = f"{acquisition.initial_quantity:,}"
    return f"{available}/{initial}"


@register.filter
def format_payment_status(acquisition):
    """Format payment status display"""
    if not acquisition:
        return "-"
    
    if acquisition.paid_from_account:
        return acquisition.paid_from_account.name
    else:
        return mark_safe('<span class="text-muted">To\'lanmagan</span>')


@register.simple_tag
def url_with_params(base_url, **kwargs):
    """Generate URL with query parameters"""
    from django.http import QueryDict
    
    query_dict = QueryDict(mutable=True)
    for key, value in kwargs.items():
        if value is not None and value != '':
            query_dict[key] = value
    
    if query_dict:
        return f"{base_url}?{query_dict.urlencode()}"
    return base_url 