from django.urls import path
from .views import AcquisitionListView

app_name = 'inventory'

urlpatterns = [
    path('acquisitions/', AcquisitionListView.as_view(), name='acquisition-list'),
] 