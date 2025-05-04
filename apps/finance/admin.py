from django.contrib import admin
from .models import Agent, Seller, TicketSale


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)
    date_hierarchy = "created_at"


@admin.register(Seller)
class SellerAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)
    date_hierarchy = "created_at"


@admin.register(TicketSale)
class TicketSaleAdmin(admin.ModelAdmin):
    list_display = (
        "sale_id",
        "sale_date",
        "get_customer_name",
        "seller",
        "ticket_purchase",
        "quantity",
        "formatted_unit_price",
        "formatted_total_price",
        "formatted_profit",
        "currency",
    )
    list_filter = ("sale_date", "customer_type", "seller", "currency")
    search_fields = ("sale_id", "customer_name", "agent__name")
    autocomplete_fields = ("agent", "ticket_purchase", "seller")
    date_hierarchy = "sale_date"

    fieldsets = (
        ("Sale Information", {"fields": ("sale_date", "seller", "customer_type")}),
        ("Customer Information", {"fields": ("customer_name", "agent")}),
        (
            "Ticket Details",
            {"fields": ("ticket_purchase", "quantity", "unit_price", "currency")},
        ),
        (
            "Additional Information",
            {"fields": ("notes", "profit"), "classes": ("collapse",)},
        ),
    )

    def get_customer_name(self, obj):
        if obj.customer_type == "agent" and obj.agent:
            return f"{obj.agent.name} (Agent)"
        return obj.customer_name

    get_customer_name.short_description = "Customer"

    def formatted_unit_price(self, obj):
        if obj.currency == "USD":
            return f"${obj.unit_price:,.2f}"
        return f"{obj.unit_price:,.2f} UZS"

    formatted_unit_price.short_description = "Unit Price"

    def formatted_total_price(self, obj):
        total = obj.total_price
        if obj.currency == "USD":
            return f"${total:,.2f}"
        return f"{total:,.2f} UZS"

    formatted_total_price.short_description = "Total Price"

    def formatted_profit(self, obj):
        if obj.profit is None:
            return "—"
        if obj.currency == "USD":
            return f"${obj.profit:,.2f}"
        return f"{obj.profit:,.2f} UZS"

    formatted_profit.short_description = "Profit"
