from django.shortcuts import render, redirect
from django.views.generic import ListView, CreateView
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Sum, Q, Value, DecimalField
from django.db.models.functions import Coalesce
from datetime import timedelta
from .models import Expenditure, FinancialAccount
from .forms import ExpenditureForm, FinancialAccountForm
from .services import ExpenditureService, FinancialAccountService
from apps.core.services import DateFilterService
import logging

logger = logging.getLogger(__name__)


class FinancialAccountListView(ListView):
    model = FinancialAccount
    template_name = 'accounting/financial_account_list.html'
    context_object_name = 'accounts'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['account_form'] = FinancialAccountForm()
        
        # Calculate totals by currency
        queryset = self.get_queryset()
        totals = queryset.aggregate(
            total_balance_uzs=Coalesce(Sum('current_balance', filter=Q(currency='UZS')), Value(0, output_field=DecimalField())),
            total_balance_usd=Coalesce(Sum('current_balance', filter=Q(currency='USD')), Value(0, output_field=DecimalField()))
        )
        context['totals'] = totals
        
        return context


class FinancialAccountCreateView(CreateView):
    model = FinancialAccount
    form_class = FinancialAccountForm
    success_url = reverse_lazy('accounting:financial-account-list')
    
    def form_valid(self, form):
        try:
            account = FinancialAccountService.create_financial_account(form.cleaned_data)
            messages.success(
                self.request, 
                f"Moliyaviy hisob '{account.name}' muvaffaqiyatli yaratildi. "
                f"Balans: {account.formatted_balance()}"
            )
            return redirect(self.success_url)
        except Exception as e:
            logger.error(f"Error creating financial account: {e}")
            messages.error(self.request, "Moliyaviy hisob yaratishda xatolik yuz berdi.")
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, "Formada xatoliklar mavjud. Iltimos, to'g'rilang.")
        return super().form_invalid(form)


class ExpenditureListView(ListView):
    model = Expenditure
    template_name = 'accounting/expenditure_list.html'
    context_object_name = 'expenditures'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related('paid_from_account').order_by('-expenditure_date')
        
        # Store filter parameters for context
        self.filter_period = self.request.GET.get('filter_period')
        self.date_filter = self.request.GET.get('date_filter')
        self.start_date = self.request.GET.get('start_date')
        self.end_date = self.request.GET.get('end_date')

        # Apply date filtering using service
        start_date, end_date = DateFilterService.get_date_range(
            self.filter_period, self.date_filter, self.start_date, self.end_date
        )
        
        return queryset.filter(expenditure_date__date__range=[start_date, end_date])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['expenditure_form'] = ExpenditureForm()
        
        # Use the service to get filter context
        filter_context = DateFilterService.get_filter_context(
            self.filter_period, self.date_filter, self.start_date, self.end_date
        )
        context.update(filter_context)

        # Calculate totals for the current filtered queryset
        filtered_queryset = self.get_queryset()
        totals = filtered_queryset.aggregate(
            total_amount_uzs=Coalesce(Sum('amount', filter=Q(currency='UZS')), Value(0, output_field=DecimalField())),
            total_amount_usd=Coalesce(Sum('amount', filter=Q(currency='USD')), Value(0, output_field=DecimalField()))
        )
        context['totals'] = totals
        
        # Preserve query parameters for pagination
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            del query_params['page']
        context['query_params'] = query_params.urlencode()

        return context


class ExpenditureCreateView(CreateView):
    model = Expenditure
    form_class = ExpenditureForm
    success_url = reverse_lazy('accounting:expenditure-list')
    
    def form_valid(self, form):
        try:
            ExpenditureService.create_expenditure(form.cleaned_data)
            messages.success(self.request, "Xarajat muvaffaqiyatli qo'shildi.")
            return redirect(self.success_url)
        except Exception as e:
            logger.error(f"Error creating expenditure: {e}")
            messages.error(self.request, "Xarajat yaratishda xatolik yuz berdi.")
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, "Formada xatoliklar mavjud. Iltimos, to'g'rilang.")
        return super().form_invalid(form)
