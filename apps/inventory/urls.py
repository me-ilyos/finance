from django.urls import path
from .views import AcquisitionListView, api_acquisitions_list
from .admin_views import delete_acquisition, edit_acquisition

app_name = 'inventory'

urlpatterns = [
    path('acquisitions/', AcquisitionListView.as_view(), name='acquisition-list'),
    path('api/acquisitions/', api_acquisitions_list, name='api-acquisitions-list'),
    path('acquisitions/<int:acquisition_id>/delete/', delete_acquisition, name='acquisition-delete'),
    path('acquisitions/<int:acquisition_id>/edit/', edit_acquisition, name='acquisition-edit'),
] 