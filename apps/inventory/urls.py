from django.urls import path
from .views import AcquisitionListView, export_acquisitions_excel

app_name = 'inventory'

urlpatterns = [
    path('acquisitions/', AcquisitionListView.as_view(), name='acquisition-list'),
    path('acquisitions/export-excel/', export_acquisitions_excel, name='acquisition-export-excel'),
] 