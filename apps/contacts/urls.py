from django.urls import path
from . import views

app_name = 'contacts'

urlpatterns = [
    # Agent URLs
    path('agents/', views.AgentListView.as_view(), name='agent-list'),
    path('agents/<int:pk>/', views.AgentDetailView.as_view(), name='agent-detail'),
    path('agents/<int:agent_pk>/add-payment/', views.add_agent_payment, name='agent-add-payment'),
    
    # Supplier URLs
    path('suppliers/', views.SupplierListView.as_view(), name='supplier-list'),
    path('suppliers/<int:pk>/', views.SupplierDetailView.as_view(), name='supplier-detail'),
    path('suppliers/<int:supplier_pk>/add-payment/', views.add_supplier_payment, name='supplier-add-payment'),
] 