from django.contrib import admin
from .models import Agent, Supplier, AgentPayment

@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'outstanding_balance_uzs', 'outstanding_balance_usd', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('name', 'phone_number', 'email')
    readonly_fields = ('outstanding_balance_uzs', 'outstanding_balance_usd', 'created_at', 'updated_at')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'contact_person', 'phone_number', 'email')
        }),
        ('Balance Information', {
            'fields': ('outstanding_balance_uzs', 'outstanding_balance_usd'),
            'classes': ('collapse',)
        }),
        ('Additional Information', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'phone_number', 'email', 'created_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('name', 'contact_person', 'phone_number', 'email')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'contact_person', 'phone_number', 'email')
        }),
        ('Additional Information', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(AgentPayment)
class AgentPaymentAdmin(admin.ModelAdmin):
    list_display = ('agent', 'payment_date', 'payment_currency', 'payment_amount', 'paid_to_account', 'related_sale', 'created_at')
    list_filter = ('payment_date', 'paid_to_account__currency', 'is_auto_created', 'created_at')
    search_fields = ('agent__name', 'notes', 'paid_to_account__name')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-payment_date', '-created_at')
    raw_id_fields = ('agent', 'paid_to_account', 'related_sale')
    
    fieldsets = (
        ('Payment Information', {
            'fields': ('agent', 'payment_date', 'related_sale')
        }),
        ('Amount Information', {
            'fields': ('amount_paid_uzs', 'amount_paid_usd', 'paid_to_account')
        }),
        ('Additional Information', {
            'fields': ('notes', 'is_auto_created')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'agent', 'paid_to_account', 'related_sale'
        )
    
    def payment_currency(self, obj):
        """Display payment currency"""
        return obj.payment_currency
    payment_currency.short_description = 'Currency'
    
    def payment_amount(self, obj):
        """Display payment amount"""
        return f"{obj.payment_amount:,.2f}"
    payment_amount.short_description = 'Amount'
