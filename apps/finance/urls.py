from django.urls import path
from . import views

app_name = "finance"

urlpatterns = [
    path("sales/", views.TicketSaleListView.as_view(), name="sale_list"),
    path("sales/create/", views.sale_create, name="sale_create"),
]
