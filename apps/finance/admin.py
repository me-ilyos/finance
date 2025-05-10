from django.contrib import admin
from .models import Agent, Seller, TicketSale, Payment, PaymentMethod


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('name', 'method_type', 'currency', 'account_number', 'is_active')
    list_filter = ('method_type', 'currency', 'is_active')
    search_fields = ('name', 'account_number', 'details')
    ordering = ('name',)


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)


@admin.register(Seller)
class SellerAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)


@admin.register(TicketSale)
class TicketSaleAdmin(admin.ModelAdmin):
    list_display = (
        'sale_id',
        'sale_date',
        'get_customer',
        'seller',
        'ticket_purchase',
        'quantity',
        'unit_price',
        'get_total_price',
        'currency',
        'formatted_profit',
    )
    list_filter = ('sale_date', 'customer_type', 'currency', 'seller')
    search_fields = ('sale_id', 'customer_name', 'agent__name', 'notes')
    date_hierarchy = 'sale_date'
    ordering = ('-sale_date',)
    
    def get_customer(self, obj):
        if obj.customer_type == 'agent' and obj.agent:
            return f"{obj.agent.name} (Agent)"
        return obj.customer_name
    get_customer.short_description = "Mijoz"
    
    def get_total_price(self, obj):
        return f"{obj.total_price} {obj.currency}"
    get_total_price.short_description = "Umumiy narx"
    
    def formatted_profit(self, obj):
        if obj.profit is None:
            return '—'
        profit = obj.profit
        if profit >= 0:
            return f"+{profit} {obj.currency}"
        return f"{profit} {obj.currency}"
    formatted_profit.short_description = "Foyda"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'payment_id',
        'payment_date',
        'ticket_sale',
        'amount',
        'currency',
        'payment_method',
        'payment_type',
    )
    list_filter = ('payment_date', 'currency', 'payment_type', 'payment_method')
    search_fields = ('payment_id', 'ticket_sale__sale_id', 'notes')
    date_hierarchy = 'payment_date'
    ordering = ('-payment_date',)
