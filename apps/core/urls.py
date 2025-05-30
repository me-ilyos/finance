from django.urls import path, include
from .views import LoginView, dashboard_view, logout_view

app_name = 'core'

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('logout/', logout_view, name='logout'),
    path('inventory/', include('apps.inventory.urls', namespace='inventory')),
] 