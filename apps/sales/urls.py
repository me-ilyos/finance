from django.urls import path
from .views import (
    SaleListView, get_accounts_for_acquisition_currency, get_sale_info,
    TicketReturnListView, TicketReturnCreateView, TicketReturnDetailView,
    create_acquisition_from_sales,
)
from .admin_views import delete_sale, edit_sale

app_name = 'sales'

urlpatterns = [
    path('', SaleListView.as_view(), name='sale-list'),
    path('acquisitions/create/', create_acquisition_from_sales, name='create-acquisition'),
    path('get-accounts/', get_accounts_for_acquisition_currency, name='get-accounts'),
    path('get-sale-info/', get_sale_info, name='get-sale-info'),
    path('<int:sale_id>/delete/', delete_sale, name='sale-delete'),
    path('<int:sale_id>/edit/', edit_sale, name='sale-edit'),
    
    # Ticket returns
    path('returns/', TicketReturnListView.as_view(), name='return_list'),
    path('returns/create/', TicketReturnCreateView.as_view(), name='return_create'),
    path('returns/<int:pk>/', TicketReturnDetailView.as_view(), name='return_detail'),
] 