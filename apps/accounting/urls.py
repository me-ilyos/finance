from django.urls import path
from .views import (
    ExpenditureListView, ExpenditureCreateView,
    FinancialAccountListView, FinancialAccountCreateView,
    api_accounts_list
)

app_name = 'accounting'

urlpatterns = [
    path('expenditures/', ExpenditureListView.as_view(), name='expenditure-list'),
    path('expenditures/create/', ExpenditureCreateView.as_view(), name='expenditure-create'),
    path('accounts/', FinancialAccountListView.as_view(), name='financial-account-list'),
    path('accounts/create/', FinancialAccountCreateView.as_view(), name='financial-account-create'),
    path('api/accounts/', api_accounts_list, name='api-accounts-list'),
] 