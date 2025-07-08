from django.urls import path
from .views import SaleListView, get_accounts_for_acquisition_currency
from .admin_views import delete_sale, edit_sale

app_name = 'sales'

urlpatterns = [
    path('', SaleListView.as_view(), name='sale-list'),
    path('ajax/get-accounts-for-acquisition/<int:acquisition_id>/', get_accounts_for_acquisition_currency, name='ajax_get_accounts_for_acquisition_currency'),
    path('<int:sale_id>/delete/', delete_sale, name='sale-delete'),
    path('<int:sale_id>/edit/', edit_sale, name='sale-edit'),
] 