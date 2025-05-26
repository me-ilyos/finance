from django.contrib import admin
from .models import FinancialAccount, Expenditure

class FinancialAccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'account_type', 'currency', 'current_balance', 'account_details')
    list_filter = ('account_type', 'currency')
    search_fields = ('name', 'account_details')
    readonly_fields = ('current_balance',)

admin.site.register(FinancialAccount, FinancialAccountAdmin)

# Register Expenditure model
class ExpenditureAdmin(admin.ModelAdmin):
    list_display = ('expenditure_date', 'description', 'amount', 'currency', 'paid_from_account')
    list_filter = ('currency', 'expenditure_date', 'paid_from_account')
    search_fields = ('description', 'notes')
    autocomplete_fields = ['paid_from_account']
    fieldsets = (
        (None, {
            'fields': ('expenditure_date', 'description', 'amount', 'currency', 'paid_from_account')
        }),
        ('Additional Information', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )

admin.site.register(Expenditure, ExpenditureAdmin)
