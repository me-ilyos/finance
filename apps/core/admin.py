from django.contrib import admin
from .models import Salesperson


@admin.register(Salesperson)
class SalespersonAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'is_active']
    list_filter = ['is_active']
    search_fields = ['user__username', 'user__first_name', 'user__last_name']
    ordering = ['user__first_name', 'user__last_name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Asosiy ma\'lumotlar', {
            'fields': ('user', 'phone_number')
        }),
        ('Status va sanalar', {
            'fields': ('is_active', 'created_at', 'updated_at')
        }),
    )
