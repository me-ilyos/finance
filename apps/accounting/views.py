from django.shortcuts import render, redirect
from django.views.generic import ListView
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Sum, Q, Value, DecimalField
from django.db.models.functions import Coalesce
from datetime import timedelta
from .models import Expenditure, FinancialAccount
from .forms import ExpenditureForm

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

        today = timezone.localdate()

        if self.filter_period == 'day' and self.date_filter:
            date_obj = timezone.datetime.strptime(self.date_filter, '%Y-%m-%d').date()
            queryset = queryset.filter(expenditure_date__date=date_obj)
        elif self.filter_period == 'week':
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            queryset = queryset.filter(expenditure_date__date__range=[start_of_week, end_of_week])
        elif self.filter_period == 'month':
            start_of_month = today.replace(day=1)
            end_of_month = (start_of_month + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            queryset = queryset.filter(expenditure_date__date__range=[start_of_month, end_of_month])
        elif self.filter_period == 'custom' and self.start_date and self.end_date:
            start_date_obj = timezone.datetime.strptime(self.start_date, '%Y-%m-%d').date()
            end_date_obj = timezone.datetime.strptime(self.end_date, '%Y-%m-%d').date()
            queryset = queryset.filter(expenditure_date__date__range=[start_date_obj, end_date_obj])
        elif not self.filter_period and not self.date_filter and not self.start_date and not self.end_date:
            # Default to today if no filter is applied
            queryset = queryset.filter(expenditure_date__date=today)
            self.date_filter = today.strftime('%Y-%m-%d') # For display in form
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['expenditure_form'] = ExpenditureForm()
        context['current_date_filter'] = self.date_filter
        context['current_start_date'] = self.start_date
        context['current_end_date'] = self.end_date
        context['filter_period'] = self.filter_period

        # Calculate totals for the current filtered queryset
        filtered_queryset = self.get_queryset() # Re-evaluate for totals
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

    def post(self, request, *args, **kwargs):
        form = ExpenditureForm(request.POST)
        if form.is_valid():
            try:
                form.save() # The model's save method handles balance updates
                messages.success(request, "Xarajat muvaffaqiyatli qo'shildi.")
                return redirect(reverse_lazy('accounting:expenditure-list'))
            except Exception as e:
                messages.error(request, f"Xarajatni saqlashda xatolik: {e}")
                # Re-populate context for rendering the page with the form and errors
                self.object_list = self.get_queryset()
                context = self.get_context_data()
                context['expenditure_form'] = form 
                return self.render_to_response(context)
        else:
            messages.error(request, "Formada xatoliklar mavjud. Iltimos, to'g'rilang.")
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            context['expenditure_form'] = form 
            return self.render_to_response(context)
