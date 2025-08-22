from django.urls import path
from . import views

app_name = 'contacts'

urlpatterns = [
    # Agent URLs
    path('agents/', views.AgentListView.as_view(), name='agent-list'),
    path('agents/<int:pk>/', views.AgentDetailView.as_view(), name='agent-detail'),
    path('agents/<int:agent_pk>/add-payment/', views.add_agent_payment, name='agent-add-payment'),
    path('agents/<int:agent_pk>/add-adjustment/', views.add_agent_adjustment, name='agent-add-adjustment'),
    
    # Supplier URLs
    path('suppliers/', views.SupplierListView.as_view(), name='supplier-list'),
    path('suppliers/<int:pk>/', views.SupplierDetailView.as_view(), name='supplier-detail'),
    path('suppliers/<int:supplier_pk>/add-payment/', views.add_supplier_payment, name='supplier-add-payment'),
    path('suppliers/<int:supplier_pk>/add-commission/', views.create_commission, name='supplier-add-commission'),
    path('suppliers/<int:supplier_pk>/add-adjustment/', views.add_supplier_adjustment, name='supplier-add-adjustment'),
    path('suppliers/<int:supplier_pk>/deactivate/', views.deactivate_supplier, name='supplier-deactivate'),
    
    # API URLs
    path('api/agents/', views.api_agents_list, name='api-agents-list'),
] 