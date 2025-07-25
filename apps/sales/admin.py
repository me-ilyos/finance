from django.contrib import admin
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.contrib.admin import actions
from .models import Sale
from .services import SaleService
import logging

logger = logging.getLogger(__name__)

class SaleAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'sale_date', 'display_ticket_info', 'quantity', 'related_acquisition',
        'buyer_display', 'salesperson_display', 'total_sale_amount', 'sale_currency', 
        'profit', 'paid_to_account'
    )
    list_filter = ('sale_date', 'sale_currency', 'agent', 'salesperson', 'paid_to_account')
    search_fields = (
        'related_acquisition__ticket__description', 'agent__name', 'client_full_name',
        'salesperson__user__username', 'salesperson__user__first_name', 'salesperson__user__last_name',
        'related_acquisition__id',
        'paid_to_account__name'
    )
    readonly_fields = ('sale_currency', 'total_sale_amount', 'profit', 'created_at', 'updated_at', 'display_ticket_description')
    fieldsets = (
        (None, {
            'fields': ('sale_date', 'salesperson', 'display_ticket_description', 'quantity', 'related_acquisition')
        }),
        ('Buyer Information', {
            'fields': ('agent', 'client_full_name', 'client_id_number')
        }),
        ('Pricing and Profit', {
            'fields': ('unit_sale_price', 'sale_currency', 'total_sale_amount', 'profit')
        }),
        ('Payment', {
            'fields': ('paid_to_account',)
        }),
        ('Other', {
            'fields': ('notes', 'created_at', 'updated_at')
        }),
    )

    def buyer_display(self, obj):
        if obj.agent:
            return obj.agent.name
        return obj.client_full_name or "N/A"
    buyer_display.short_description = "Buyer"

    def display_ticket_info(self, obj):
        if obj.related_acquisition and obj.related_acquisition.ticket:
            return str(obj.related_acquisition.ticket)
        return "N/A"
    display_ticket_info.short_description = "Ticket Info"

    def display_ticket_description(self, obj):
        if obj.related_acquisition and obj.related_acquisition.ticket:
            return obj.related_acquisition.ticket.description
        return "N/A"
    display_ticket_description.short_description = "Ticket Description"

    def salesperson_display(self, obj):
        if obj.salesperson:
            return obj.salesperson.user.get_full_name() or obj.salesperson.user.username
        return "N/A"
    salesperson_display.short_description = "Salesperson"

    # Override default actions to use our custom deletion
    actions = ['delete_selected_sales', 'test_debt_removal']

    def test_debt_removal(self, request, queryset):
        """Test action to verify debt removal logic without actually deleting"""
        if not request.user.is_superuser:
            messages.error(request, "Only superusers can run this test.")
            return
            
        for sale in queryset:
            if sale.agent:
                messages.info(request, 
                    f"Sale #{sale.id}: Agent {sale.agent.name} would have "
                    f"{sale.total_sale_amount} {sale.sale_currency} debt reduced. "
                    f"Current balance: UZS={sale.agent.balance_uzs}, USD={sale.agent.balance_usd}")
            else:
                messages.info(request, f"Sale #{sale.id}: No agent debt to remove")
    test_debt_removal.short_description = "Test debt removal (without deleting)"

    def delete_selected_sales(self, request, queryset):
        """Custom delete selected action that uses SaleService"""
        return self.delete_queryset(request, queryset)
    delete_selected_sales.short_description = "Delete selected sales (with proper debt handling)"

    def delete_model(self, request, obj):
        """Override delete_model to use SaleService for proper debt handling"""
        logger.info(f"Admin delete_model called for sale {obj.id} with agent: {obj.agent}")
        try:
            SaleService.delete_sale(obj.id, request.user)
            messages.success(request, f"Sale #{obj.id} successfully deleted with proper debt handling.")
        except ValidationError as e:
            messages.error(request, str(e))
        except Exception as e:
            logger.error(f"Error in delete_model for sale {obj.id}: {str(e)}")
            messages.error(request, f"Error deleting sale: {str(e)}")

    def delete_queryset(self, request, queryset):
        """Override delete_queryset to use SaleService for proper debt handling"""
        logger.info(f"Admin delete_queryset called for {queryset.count()} sales")
        success_count = 0
        error_count = 0
        
        for obj in queryset:
            logger.info(f"Deleting sale {obj.id} with agent: {obj.agent}")
            try:
                SaleService.delete_sale(obj.id, request.user)
                success_count += 1
            except ValidationError as e:
                logger.error(f"ValidationError deleting sale {obj.id}: {str(e)}")
                messages.error(request, f"Sale #{obj.id}: {str(e)}")
                error_count += 1
            except Exception as e:
                logger.error(f"Exception deleting sale {obj.id}: {str(e)}")
                messages.error(request, f"Sale #{obj.id}: Error deleting - {str(e)}")
                error_count += 1
        
        if success_count > 0:
            messages.success(request, f"{success_count} sale(s) successfully deleted with proper debt handling.")
        if error_count > 0:
            messages.warning(request, f"{error_count} sale(s) could not be deleted.")

    def get_actions(self, request):
        """Override to remove default delete_selected and use our custom one"""
        actions = super().get_actions(request)
        # Remove default delete_selected action
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

admin.site.register(Sale, SaleAdmin)
