from django.urls import path
from . import views

app_name = "finance"

urlpatterns = [
    path("sales/", views.TicketSaleListView.as_view(), name="sale_list"),
    path("sales/create/", views.sale_create, name="sale_create"),
    path("sales/export/", views.export_sales_to_excel, name="export_sales"),
    path("payments/", views.PaymentListView.as_view(), name="payment_list"),
    
    # Payment methods management
    path("payment-methods/", views.PaymentMethodListView.as_view(), name="payment_method_list"),
    path("payment-methods/create/", views.payment_method_create, name="payment_method_create"),
    path("payment-methods/<int:pk>/update/", views.payment_method_update, name="payment_method_update"),
    path("payment-methods/<int:pk>/toggle-status/", views.payment_method_toggle_status, name="payment_method_toggle_status"),
    path("hisob-kitob/", views.FinancialReportView.as_view(), name="financial_report"),
]
