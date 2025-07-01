from django.urls import path
from .views import (
    LoginView, SalespersonListView, SalespersonDetailView, dashboard_view, logout_view, 
    salesperson_export_excel, salesperson_edit, salesperson_toggle_status
)

app_name = 'core'

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('salespeople/', SalespersonListView.as_view(), name='salesperson-list'),
    path('salespeople/<int:salesperson_id>/', SalespersonDetailView.as_view(), name='salesperson-detail'),
    path('salespeople/export-excel/', salesperson_export_excel, name='salesperson-export-excel'),
    path('salespeople/<int:salesperson_id>/edit/', salesperson_edit, name='salesperson-edit'),
    path('salespeople/<int:salesperson_id>/toggle-status/', salesperson_toggle_status, name='salesperson-toggle-status'),
    path('logout/', logout_view, name='logout'),
] 