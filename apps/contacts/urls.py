from django.urls import path
from . import views

app_name = 'contacts'

urlpatterns = [
    path('agents/', views.AgentListView.as_view(), name='agent-list'),
    path('agents/add/', views.AgentCreateView.as_view(), name='agent-add'),
    path('agents/<int:pk>/', views.AgentDetailView.as_view(), name='agent-detail'),
    path('agents/<int:pk>/edit/', views.AgentUpdateView.as_view(), name='agent-edit'),
    path('agents/<int:agent_pk>/add-payment/', views.add_agent_payment, name='agent-add-payment'),
    path('suppliers/', views.SupplierListView.as_view(), name='supplier-list'),
] 