from django.urls import path
from .views import AgentListView, SupplierListView

app_name = 'contacts'

urlpatterns = [
    path('agents/', AgentListView.as_view(), name='agent-list'),
    path('suppliers/', SupplierListView.as_view(), name='supplier-list'),
] 