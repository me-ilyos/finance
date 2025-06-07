from django.urls import path
from .views import SaleListView, get_accounts_for_acquisition_currency, export_sales_excel

app_name = 'sales'

urlpatterns = [
    path('', SaleListView.as_view(), name='sale-list'),
    path('ajax/get-accounts-for-acquisition/<int:acquisition_id>/', get_accounts_for_acquisition_currency, name='ajax_get_accounts_for_acquisition_currency'),
    path('export-excel/', export_sales_excel, name='sale-export-excel'),
] 