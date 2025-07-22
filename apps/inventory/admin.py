from django.contrib import admin
from .models import Ticket, Acquisition


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'ticket_type', 'description', 'departure_date_time', 'arrival_date_time', 'is_active', 'created_at')
    list_filter = ('ticket_type', 'departure_date_time', 'is_active')
    search_fields = ('description',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Basic Information', {
            'fields': ('ticket_type', 'description')
        }),
        ('Schedule', {
            'fields': ('departure_date_time', 'arrival_date_time')
        }),
        ('Status & Timestamps', {
            'fields': ('is_active', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Acquisition)
class AcquisitionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'ticket',
        'supplier',
        'salesperson',
        'acquisition_date',
        'initial_quantity',
        'available_quantity',
        'currency',
        'unit_price',
        'total_amount',
        'paid_from_account',
        'created_at'
    )
    search_fields = ('ticket__description', 'supplier__name', 'salesperson__user__username', 'salesperson__user__first_name', 'salesperson__user__last_name')
    list_filter = ('acquisition_date', 'currency', 'supplier', 'ticket__ticket_type', 'salesperson')
    readonly_fields = ('total_amount', 'available_quantity', 'created_at', 'updated_at')
    raw_id_fields = ('ticket', 'supplier', 'paid_from_account', 'salesperson')
    fieldsets = (
        ('Core Information', {
            'fields': ('ticket', 'supplier', 'salesperson', 'acquisition_date', 'initial_quantity')
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
