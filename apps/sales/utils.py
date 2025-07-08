from django.db.models import Sum, Case, When, Value, DecimalField


def calculate_sales_totals(queryset):
    """Calculate totals for sales queryset"""
    return queryset.aggregate(
        total_quantity=Sum('quantity'),
        total_sum_uzs=Sum(
            Case(When(sale_currency='UZS', then='total_sale_amount'), 
                 default=Value(0), output_field=DecimalField())
        ),
        total_sum_usd=Sum(
            Case(When(sale_currency='USD', then='total_sale_amount'), 
                 default=Value(0), output_field=DecimalField())
        ),
        total_profit_uzs=Sum(
            Case(When(sale_currency='UZS', then='profit'), 
                 default=Value(0), output_field=DecimalField())
        ),
        total_profit_usd=Sum(
            Case(When(sale_currency='USD', then='profit'), 
                 default=Value(0), output_field=DecimalField())
        )
    ) 