from django.urls import path
from . import views

app_name = "stock"

urlpatterns = [
    path("purchases/", views.TicketPurchaseListView.as_view(), name="purchase_list"),
    path("purchases/create/", views.purchase_create, name="purchase_create"),
]
