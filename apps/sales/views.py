from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView
from django.contrib import messages
from .models import Sale
from .forms import SaleForm
from .services import SaleService
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal
from django.http import JsonResponse
from apps.inventory.models import Acquisition
from apps.accounting.models import FinancialAccount
from django.db.models import Sum, Case, When, Value, DecimalField
from django.core.exceptions import ValidationError
from apps.core.services import DateFilterService
import logging

logger = logging.getLogger(__name__)


class SaleListView(ListView):
    model = Sale
    template_name = 'sales/sale_list.html'
    context_object_name = 'sales'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'related_acquisition', 
            'related_acquisition__ticket',
            'agent', 
            'paid_to_account'
        ).order_by('-sale_date', '-created_at')
        
        # Store filter parameters for context
        self.filter_period = self.request.GET.get('filter_period')
        self.date_filter = self.request.GET.get('date_filter')
        self.start_date = self.request.GET.get('start_date')
        self.end_date = self.request.GET.get('end_date')

        # Apply date filtering using service
        start_date, end_date = DateFilterService.get_date_range(
            self.filter_period, self.date_filter, self.start_date, self.end_date
        )
        
        return queryset.filter(sale_date__date__range=[start_date, end_date])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if 'sale_form' not in context:
            context['sale_form'] = SaleForm()
        
        # Use the service to get filter context
        filter_context = DateFilterService.get_filter_context(
            self.filter_period, self.date_filter, self.start_date, self.end_date
        )
        context.update(filter_context)

        # Calculate totals for the current filtered queryset
        filtered_queryset = self.get_queryset()
        totals = filtered_queryset.aggregate(
            total_quantity=Sum('quantity'),
            total_sum_uzs=Sum(
                Case(When(sale_currency='UZS', then='total_sale_amount'), 
                     default=Value(0), output_field=DecimalField())
            ),
            total_sum_usd=Sum(
                Case(When(sale_currency='USD', then='total_sale_amount'), 
                     default=Value(0), output_field=DecimalField())
            ),
            total_profit_uzs=Sum(
                Case(When(sale_currency='UZS', then='profit'), 
                     default=Value(0), output_field=DecimalField())
            ),
            total_profit_usd=Sum(
                Case(When(sale_currency='USD', then='profit'), 
                     default=Value(0), output_field=DecimalField())
            ),
            total_initial_payment_uzs=Sum(
                Case(When(agent__isnull=False, sale_currency='UZS', then='initial_payment_amount'), 
                     default=Value(0), output_field=DecimalField())
            ),
            total_initial_payment_usd=Sum(
                Case(When(agent__isnull=False, sale_currency='USD', then='initial_payment_amount'), 
                     default=Value(0), output_field=DecimalField())
            )
        )
        context['totals'] = totals
        
        # Preserve query parameters for pagination
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            del query_params['page']
        context['query_params'] = query_params.urlencode()
        
        return context

    def post(self, request, *args, **kwargs):
        """Handle sale creation using service layer"""
        form = SaleForm(request.POST)
        if form.is_valid():
            try:
                sale = form.save()
                if sale:
                    messages.success(request, "Yangi sotuv muvaffaqiyatli qo'shildi.")
                    return redirect(reverse_lazy('sales:sale-list'))
                else:
                    messages.error(request, "Sotuvni saqlashda xatolik yuz berdi.")
            except ValidationError as e:
                logger.error(f"Validation error creating sale: {e}")
                messages.error(request, f"Sotuvni saqlashda xatolik: {e}")
            except Exception as e:
                logger.error(f"Unexpected error creating sale: {e}")
                messages.error(request, "Kutilmagan xatolik yuz berdi.")
        else:
            logger.warning(f"Invalid form data: {form.errors}")

        # Re-render with form errors
        self.object_list = self.get_queryset()
        context = self.get_context_data(sale_form=form, object_list=self.object_list)
        
        if not messages.get_messages(request):
            messages.error(request, "Sotuvni qo'shishda xatolik. Iltimos, ma'lumotlarni tekshiring.")
        
        return self.render_to_response(context)


def get_accounts_for_acquisition_currency(request, acquisition_id):
    """AJAX view to get accounts matching acquisition currency"""
    try:
        acquisition = Acquisition.objects.get(pk=acquisition_id)
        currency = acquisition.currency
        accounts = FinancialAccount.objects.filter(
            currency=currency, 
            is_active=True
        ).values('id', 'name')
        
        return JsonResponse(list(accounts), safe=False)
        
    except Acquisition.DoesNotExist:
        return JsonResponse({'error': 'Acquisition not found'}, status=404)
    except Exception as e:
        logger.error(f"Error in get_accounts_for_acquisition_currency: {e}")
        return JsonResponse({'error': str(e)}, status=500)
