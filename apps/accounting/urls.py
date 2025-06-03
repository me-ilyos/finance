from django.urls import path
from .views import (
    ExpenditureListView, ExpenditureCreateView,
    FinancialAccountListView, FinancialAccountCreateView
)
# from .views import SomeView # Example: Import your views here

app_name = 'accounting'

urlpatterns = [
    path('expenditures/', ExpenditureListView.as_view(), name='expenditure-list'),
    path('expenditures/create/', ExpenditureCreateView.as_view(), name='expenditure-create'),
    path('accounts/', FinancialAccountListView.as_view(), name='financial-account-list'),
    path('accounts/create/', FinancialAccountCreateView.as_view(), name='financial-account-create'),
    # path('some-path/', SomeView.as_view(), name='some-view'), # Example
] 