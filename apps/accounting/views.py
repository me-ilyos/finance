from django.shortcuts import render, redirect
from django.views.generic import ListView, CreateView
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Sum, Q, Value, DecimalField
from django.db.models.functions import Coalesce
from datetime import timedelta
from .models import Expenditure, FinancialAccount
from .forms import ExpenditureForm
from apps.core.services import DateFilterService


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
        messages.success(self.request, "Xarajat muvaffaqiyatli qo'shildi.")
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, "Formada xatoliklar mavjud. Iltimos, to'g'rilang.")
        # Redirect back to list view with form errors
        return redirect(self.success_url)
