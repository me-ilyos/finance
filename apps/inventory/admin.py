from django.contrib import admin
from .models import Ticket, Acquisition

class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'ticket_type', 'description', 'departure_date_time', 'arrival_date_time', 'created_at')
    search_fields = ('description',)
    list_filter = ('ticket_type', 'departure_date_time', 'arrival_date_time')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('ticket_type', 'description', 'departure_date_time', 'arrival_date_time')
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at'),
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
        'currency',
        'unit_price',
        'total_amount',
        'paid_from_account',
        'created_at'
    )
    search_fields = ('ticket__description', 'supplier__name')
    list_filter = ('acquisition_date', 'currency', 'supplier', 'ticket__ticket_type')
    readonly_fields = ('total_amount', 'available_quantity', 'created_at', 'updated_at')
    raw_id_fields = ('ticket', 'supplier', 'paid_from_account')
    fieldsets = (
        ('Core Information', {
            'fields': ('ticket', 'supplier', 'acquisition_date', 'initial_quantity')
        }),
        ('Pricing', {
            'fields': ('unit_price', 'currency', 'total_amount')
        }),
        ('Stock & Payment', {
            'fields': ('available_quantity', 'paid_from_account')
        }),
        ('Notes & Timestamps', {
            'fields': ('notes', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        """Make total_amount and available_quantity readonly"""
        readonly = list(super().get_readonly_fields(request, obj))
        if obj:  # Editing existing object
            readonly.extend(['total_amount', 'available_quantity'])
        return readonly

admin.site.register(Ticket, TicketAdmin)
admin.site.register(Acquisition, AcquisitionAdmin)
