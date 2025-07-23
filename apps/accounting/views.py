from django.shortcuts import redirect
from django.views.generic import ListView, CreateView
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Sum, Q, Value, DecimalField
from django.db.models.functions import Coalesce
from .models import Expenditure, FinancialAccount
from .forms import ExpenditureForm, FinancialAccountForm
from apps.core.services import DateFilterService


class FinancialAccountListView(ListView):
    model = FinancialAccount
    template_name = 'accounting/financial_account_list.html'
    context_object_name = 'accounts'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Only provide account form to superusers (admins)
        if self.request.user.is_superuser:
            context['account_form'] = FinancialAccountForm()
        
        queryset = self.get_queryset()
        totals = queryset.aggregate(
            total_balance_uzs=Coalesce(Sum('current_balance', filter=Q(currency='UZS')), Value(0, output_field=DecimalField())),
            total_balance_usd=Coalesce(Sum('current_balance', filter=Q(currency='USD')), Value(0, output_field=DecimalField()))
        )
        context['totals'] = totals
        
        return context


class FinancialAccountCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = FinancialAccount
    form_class = FinancialAccountForm
    success_url = reverse_lazy('accounting:financial-account-list')
    login_url = '/core/login/'
    
    def test_func(self):
        """Only allow superusers (admins) to create financial accounts"""
        return self.request.user.is_superuser
    
    def form_valid(self, form):
        try:
            form.save()
            return redirect(self.success_url)
        except:
            return self.form_invalid(form)


class ExpenditureListView(ListView):
    model = Expenditure
    template_name = 'accounting/expenditure_list.html'
    context_object_name = 'expenditures'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related('paid_from_account').order_by('-expenditure_date')
        
        self.filter_period = self.request.GET.get('filter_period')
        self.date_filter = self.request.GET.get('date_filter')
        self.start_date = self.request.GET.get('start_date')
        self.end_date = self.request.GET.get('end_date')

        start_date, end_date = DateFilterService.get_date_range(
            self.filter_period, self.date_filter, self.start_date, self.end_date
        )
        
        return queryset.filter(expenditure_date__date__range=[start_date, end_date])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['expenditure_form'] = ExpenditureForm()
        
        filter_context = DateFilterService.get_filter_context(
            self.filter_period, self.date_filter, self.start_date, self.end_date
        )
        context.update(filter_context)

        filtered_queryset = self.get_queryset()
        totals = filtered_queryset.aggregate(
            total_amount_uzs=Coalesce(Sum('amount', filter=Q(currency='UZS')), Value(0, output_field=DecimalField())),
            total_amount_usd=Coalesce(Sum('amount', filter=Q(currency='USD')), Value(0, output_field=DecimalField()))
        )
        context['totals'] = totals
        
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
            form.save()
            return redirect(self.success_url)
        except:
            return self.form_invalid(form)


@login_required(login_url='/core/login/')
def api_accounts_list(request):
    accounts = FinancialAccount.objects.filter(is_active=True).values(
        'id', 'name', 'currency'
    ).order_by('currency', 'name')
    
    result = []
    for account in accounts:
        result.append({
            'id': account['id'],
            'name': f"{account['name']} ({account['currency']})"
        })
    
    return JsonResponse(result, safe=False)
