from django import template
from django.utils.safestring import mark_safe

register = template.Library()


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