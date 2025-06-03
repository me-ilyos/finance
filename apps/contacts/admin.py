from django.contrib import admin
from .models import Agent, Supplier, AgentPayment

@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'outstanding_balance_uzs', 'outstanding_balance_usd', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'phone_number')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'current_balance_uzs', 'current_balance_usd', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'phone_number')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)

@admin.register(AgentPayment)
class AgentPaymentAdmin(admin.ModelAdmin):
    list_display = ('agent', 'payment_date', 'payment_currency', 'payment_amount', 'paid_to_account')
    list_filter = ('payment_date', 'paid_to_account__currency')
    search_fields = ('agent__name', 'paid_to_account__name')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-payment_date',)
    raw_id_fields = ('agent', 'paid_to_account')

    def payment_currency(self, obj):
        return obj.payment_currency or 'N/A'
    payment_currency.short_description = 'Currency'
    
    def payment_amount(self, obj):
        return f"{obj.payment_amount:,.2f}"
    payment_amount.short_description = 'Amount'
