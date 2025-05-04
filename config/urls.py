from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("stock/", include("apps.stock.urls")),
    path("finance/", include("apps.finance.urls")),
    path("", RedirectView.as_view(pattern_name="finance:sale_list"), name="home"),
]
