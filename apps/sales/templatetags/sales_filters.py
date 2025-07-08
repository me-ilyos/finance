from django import template

register = template.Library()





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
def ticket_description_short(acquisition):
    """Get short ticket description"""
    if not acquisition or not acquisition.ticket:
        return "N/A"
    return acquisition.ticket.description[:25] + "..." if len(acquisition.ticket.description) > 25 else acquisition.ticket.description 