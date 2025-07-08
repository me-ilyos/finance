from django.urls import path
from .views import (
    LoginView, dashboard_view, logout_view, 
    SalespersonListView, SalespersonDetailView, 
    salesperson_export_excel, salesperson_edit, 
    salesperson_toggle_status, transfer_money, 
    get_transfer_form
)

app_name = 'core'

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('logout/', logout_view, name='logout'),
    
    # Transfer URLs
    path('transfer/', transfer_money, name='transfer-money'),
    path('transfer/form/', get_transfer_form, name='transfer-form'),
    
    # Salesperson URLs
    path('salesperson/', SalespersonListView.as_view(), name='salesperson-list'),
    path('salesperson/<int:pk>/', SalespersonDetailView.as_view(), name='salesperson-detail'),
    path('salesperson/export/', salesperson_export_excel, name='salesperson-export'),
    path('salesperson/<int:salesperson_id>/edit/', salesperson_edit, name='salesperson-edit'),
    path('salesperson/<int:salesperson_id>/toggle-status/', salesperson_toggle_status, name='salesperson-toggle-status'),
] 