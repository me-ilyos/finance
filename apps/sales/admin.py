from django.contrib import admin
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.contrib.admin import actions
from .models import Sale, TicketReturn
from .services import SaleService
import logging

logger = logging.getLogger(__name__)

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'sale_date', 'quantity', 'unit_sale_price', 'total_sale_amount', 
        'sale_currency', 'agent', 'client_full_name', 'salesperson', 'profit'
    ]
    list_filter = ['sale_currency', 'sale_date', 'agent', 'salesperson']
    search_fields = ['client_full_name', 'agent__name', 'related_acquisition__ticket__description']
    readonly_fields = ['total_sale_amount', 'profit', 'sale_currency', 'created_at', 'updated_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'agent', 'related_acquisition__ticket', 'related_acquisition__supplier', 'salesperson'
        )


@admin.register(TicketReturn)
class TicketReturnAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'original_sale', 'return_date', 'quantity_returned', 
        'fine_amount', 'fine_currency', 'supplier_fine_amount', 'supplier_fine_currency',
        'is_agent_return', 'is_customer_return'
    ]
    list_filter = ['return_date', 'fine_currency', 'supplier_fine_currency']
    search_fields = [
        'original_sale__id', 'original_sale__client_full_name', 
        'original_sale__agent__name', 'notes'
    ]
    readonly_fields = [
        'fine_currency', 'supplier_fine_currency', 'total_fine_amount', 
        'total_supplier_fine_amount', 'returned_sale_amount', 'created_at', 'updated_at'
    ]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'original_sale__agent', 
            'original_sale__related_acquisition__ticket',
            'original_sale__related_acquisition__supplier',
            'fine_paid_to_account'
        )
    
    def is_agent_return(self, obj):
        return obj.is_agent_return
    is_agent_return.boolean = True
    is_agent_return.short_description = "Agent qaytarishi"
    
    def is_customer_return(self, obj):
        return obj.is_customer_return
    is_customer_return.boolean = True
    is_customer_return.short_description = "Mijoz qaytarishi"
