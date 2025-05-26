from django.contrib import admin
from .models import Ticket, Acquisition

class TicketAdmin(admin.ModelAdmin):
    list_display = ('identifier', 'ticket_type', 'description', 'departure_date_time', 'arrival_date_time', 'created_at')
    search_fields = ('identifier', 'description')
    list_filter = ('ticket_type', 'departure_date_time', 'arrival_date_time')
    readonly_fields = ('identifier', 'created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('ticket_type', 'description', 'departure_date_time', 'arrival_date_time')
        }),
        ('System Information', {
            'fields': ('identifier', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

class AcquisitionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'ticket',
        'supplier',
        'acquisition_date',
        'initial_quantity',
        'available_quantity',
        'transaction_currency',
        'get_unit_price',
        'total_amount',
        'paid_from_account',
        'created_at'
    )
    search_fields = ('ticket__identifier', 'ticket__description', 'supplier__name')
    list_filter = ('acquisition_date', 'transaction_currency', 'supplier', 'ticket__ticket_type')
    readonly_fields = ('total_amount', 'available_quantity', 'created_at', 'updated_at')
    raw_id_fields = ('ticket', 'supplier', 'paid_from_account') # For better performance with many related objects
    fieldsets = (
        ('Core Information', {
            'fields': ('ticket', 'supplier', 'acquisition_date', 'initial_quantity', 'transaction_currency', 'unit_price_uzs', 'unit_price_usd')
        }),
        ('Financials & Stock', {
            'fields': ('total_amount', 'available_quantity', 'paid_from_account')
        }),
        ('Notes & Timestamps', {
            'fields': ('notes', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_unit_price(self, obj):
        if obj.transaction_currency == Acquisition.Currency.UZS and obj.unit_price_uzs is not None:
            return f"{obj.unit_price_uzs} UZS"
        elif obj.transaction_currency == Acquisition.Currency.USD and obj.unit_price_usd is not None:
            return f"{obj.unit_price_usd} USD"
        return "N/A"
    get_unit_price.short_description = 'Unit Price'

admin.site.register(Ticket, TicketAdmin)
admin.site.register(Acquisition, AcquisitionAdmin)
