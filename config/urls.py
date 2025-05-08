from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.contrib.auth.decorators import login_required
from apps.stock.views import CustomLoginView, logout_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("stock/", include("apps.stock.urls")),
    path("finance/", include("apps.finance.urls")),
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", logout_view, name="logout"),
    path("", RedirectView.as_view(pattern_name="login"), name="home"),
]
