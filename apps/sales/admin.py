from django.contrib import admin
from .models import Sale

class SaleAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'sale_date', 'display_ticket_info', 'quantity', 'related_acquisition',
        'buyer_display', 'total_sale_amount', 'sale_currency', 
        'profit', 'paid_to_account'
    )
    list_filter = ('sale_date', 'sale_currency', 'agent', 'paid_to_account')
    search_fields = (
        'related_acquisition__ticket__description', 'agent__name', 'client_full_name',
        'related_acquisition__id',
        'paid_to_account__name'
    )
    readonly_fields = ('sale_currency', 'total_sale_amount', 'profit', 'created_at', 'updated_at', 'display_ticket_description')
    fieldsets = (
        (None, {
            'fields': ('sale_date', 'display_ticket_description', 'quantity', 'related_acquisition')
        }),
        ('Buyer Information', {
            'fields': ('agent', 'client_full_name', 'client_id_number')
        }),
        ('Pricing and Profit', {
            'fields': ('unit_sale_price', 'sale_currency', 'total_sale_amount', 'profit')
        }),
        ('Payment', {
            'fields': ('paid_to_account',)
        }),
        ('Other', {
            'fields': ('notes', 'created_at', 'updated_at')
        }),
    )

    def buyer_display(self, obj):
        if obj.agent:
            return obj.agent.name
        return obj.client_full_name or "N/A"
    buyer_display.short_description = "Buyer"

    def display_ticket_info(self, obj):
        if obj.related_acquisition and obj.related_acquisition.ticket:
            return str(obj.related_acquisition.ticket)
        return "N/A"
    display_ticket_info.short_description = "Ticket Info"

    def display_ticket_description(self, obj):
        if obj.related_acquisition and obj.related_acquisition.ticket:
            return obj.related_acquisition.ticket.description
        return "N/A"
    display_ticket_description.short_description = "Ticket Description"

admin.site.register(Sale, SaleAdmin)
