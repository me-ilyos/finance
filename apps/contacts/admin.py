from django.contrib import admin
from .models import Agent, Supplier, AgentPayment

@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'outstanding_balance_uzs', 'outstanding_balance_usd', 'created_at', 'updated_at')
    search_fields = ('name', 'phone_number')
    readonly_fields = ('outstanding_balance_uzs', 'outstanding_balance_usd')
    ordering = ('-created_at',)

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'created_at')
    search_fields = ('name', 'phone_number')
    ordering = ('-created_at',)

@admin.register(AgentPayment)
class AgentPaymentAdmin(admin.ModelAdmin):
    list_display = ('agent', 'payment_date', 'amount_paid_uzs', 'amount_paid_usd', 'paid_to_account', 'created_at')
    list_filter = ('payment_date', 'agent', 'paid_to_account')
    search_fields = ('agent__name', 'notes')
    ordering = ('-payment_date',)
    raw_id_fields = ('agent', 'paid_to_account')

    fieldsets = (
        (None, {
            'fields': ('agent', 'payment_date')
        }),
        ('Payment Amount', {
            'fields': (('amount_paid_uzs', 'amount_paid_usd'), 'paid_to_account')
        }),
        ('Additional Information', {
            'fields': ('notes',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('agent', 'paid_to_account')
