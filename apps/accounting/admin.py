from django.contrib import admin
from .models import FinancialAccount, Expenditure

@admin.register(FinancialAccount)
class FinancialAccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'account_type', 'currency', 'current_balance', 'is_active', 'created_at')
    list_filter = ('account_type', 'currency', 'is_active')
    search_fields = ('name', 'account_details')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Asosiy Ma\'lumotlar', {
            'fields': ('name', 'account_type', 'currency')
        }),
        ('Moliyaviy Ma\'lumotlar', {
            'fields': ('current_balance',),
            'description': 'Balansni faqat yangi hisob yaratishda kiriting yoki ehtiyotkorlik bilan o\'zgartiring. Balans odatda to\'lovlar va xarajatlar orqali avtomatik yangilanadi.'
        }),
        ('Qo\'shimcha Ma\'lumotlar', {
            'fields': ('account_details', 'is_active')
        }),
        ('Vaqt Belgilari', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        """Make current_balance readonly after creation unless superuser"""
        readonly_fields = list(self.readonly_fields)
        if obj and not request.user.is_superuser:  # editing an existing object and not superuser
            readonly_fields.append('current_balance')
        return readonly_fields

@admin.register(Expenditure)
class ExpenditureAdmin(admin.ModelAdmin):
    list_display = ('expenditure_date', 'description', 'amount', 'currency', 'paid_from_account', 'created_at')
    list_filter = ('currency', 'paid_from_account', 'expenditure_date')
    search_fields = ('description', 'notes', 'paid_from_account__name')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ['paid_from_account'] # For easier account selection
    fieldsets = (
        (None, {
            'fields': ('expenditure_date', 'description', 'amount', 'currency', 'paid_from_account')
        }),
        ('Additional Information', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('paid_from_account')
