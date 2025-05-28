from django.urls import path
from .views import AgentListView, SupplierListView, AgentDetailView

app_name = 'contacts'

urlpatterns = [
    path('agents/', AgentListView.as_view(), name='agent-list'),
    path('agents/<int:pk>/', AgentDetailView.as_view(), name='agent-detail'),
    path('suppliers/', SupplierListView.as_view(), name='supplier-list'),
] 