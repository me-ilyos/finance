from django.contrib import admin
from .models import Supplier, Agent

class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'created_at', 'updated_at')
    search_fields = ('name', 'phone_number')
    list_filter = ('created_at', 'updated_at')

class AgentAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'outstanding_balance_uzs', 'outstanding_balance_usd', 'created_at', 'updated_at')
    search_fields = ('name', 'phone_number')
    list_filter = ('created_at', 'updated_at')
    readonly_fields = ('outstanding_balance_uzs', 'outstanding_balance_usd')

admin.site.register(Supplier, SupplierAdmin)
admin.site.register(Agent, AgentAdmin)
