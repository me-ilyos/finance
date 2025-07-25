from django.contrib import admin
from .models import Agent, Supplier, AgentPayment, SupplierPayment, Commission

@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'initial_balance_uzs', 'initial_balance_usd', 'balance_uzs', 'balance_usd', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'phone_number')
    readonly_fields = ('initial_balance_uzs', 'initial_balance_usd', 'created_at', 'updated_at')
    ordering = ('-created_at',)

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'is_active', 'initial_balance_uzs', 'initial_balance_usd', 'balance_uzs', 'balance_usd', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'phone_number')
    readonly_fields = ('initial_balance_uzs', 'initial_balance_usd', 'created_at', 'updated_at')
    ordering = ('-created_at',)

@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    list_display = ('supplier', 'acquisition', 'commission_date', 'amount', 'currency', 'created_at')
    list_filter = ('commission_date', 'currency', 'supplier')
    search_fields = ('supplier__name', 'acquisition__ticket__description')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-commission_date',)
    raw_id_fields = ('supplier', 'acquisition')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('supplier', 'acquisition__ticket')

@admin.register(SupplierPayment)
class SupplierPaymentAdmin(admin.ModelAdmin):
    list_display = ('supplier', 'payment_date', 'amount', 'currency', 'paid_from_account')
    list_filter = ('payment_date', 'currency')
    search_fields = ('supplier__name', 'paid_from_account__name')
    readonly_fields = ('created_at',)
    ordering = ('-payment_date',)
    raw_id_fields = ('supplier', 'paid_from_account')

@admin.register(AgentPayment)
class AgentPaymentAdmin(admin.ModelAdmin):
    list_display = ('agent', 'payment_date', 'amount', 'currency', 'paid_to_account')
    list_filter = ('payment_date', 'currency')
    search_fields = ('agent__name', 'paid_to_account__name')
    readonly_fields = ('created_at',)
    ordering = ('-payment_date',)
    raw_id_fields = ('agent', 'paid_to_account')
