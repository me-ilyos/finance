from django.contrib import admin
from .models import Supplier, TicketPurchase


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "purchase_count")
    search_fields = ("name",)
    list_filter = ("created_at",)
    date_hierarchy = "created_at"

    def purchase_count(self, obj):
        count = obj.ticket_purchases.count()
        return count

    purchase_count.short_description = "Xaridlar soni"


@admin.register(TicketPurchase)
class TicketPurchaseAdmin(admin.ModelAdmin):
    list_display = (
        "purchase_id",
        "supplier",
        "purchase_date",
        "quantity",
        "formatted_unit_price",
        "formatted_total_price",
        "currency",
    )
    list_filter = ("purchase_date", "supplier", "currency")
    search_fields = ("purchase_id", "supplier__name", "commentary")
    autocomplete_fields = ("supplier",)
    date_hierarchy = "purchase_date"

    # Since purchase_id is now auto-generated, we don't include it in fields
    fieldsets = (
        ("Asosiy ma'lumot", {"fields": ("supplier", "purchase_date")}),
        ("Xarid tafsilotlari", {"fields": ("quantity", "unit_price", "currency")}),
        (
            "Qo'shimcha ma'lumot",
            {"fields": ("commentary",), "classes": ("collapse",)},
        ),
    )

    def formatted_unit_price(self, obj):
        if obj.currency == "USD":
            return f"${obj.unit_price:,.2f}"
        return f"{obj.unit_price:,.2f} UZS"

    formatted_unit_price.short_description = "Narxi"

    def formatted_total_price(self, obj):
        total = obj.quantity * obj.unit_price
        if obj.currency == "USD":
            return f"${total:,.2f}"
        return f"{total:,.2f} UZS"

    formatted_total_price.short_description = "Umumiy narx"
