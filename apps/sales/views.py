from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView
from django.contrib import messages
from .models import Sale
from .forms import SaleForm # Import the SaleForm
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal
from django.http import JsonResponse
from apps.inventory.models import Acquisition # For fetching Acquisition instance
from apps.accounting.models import FinancialAccount # For fetching FinancialAccount instances
from django.db.models import Sum, Case, When, Value, DecimalField
from django.core.exceptions import ValidationError # <--- Import ValidationError

class SaleListView(ListView):
    model = Sale
    template_name = 'sales/sale_list.html' # Template for listing sales
    context_object_name = 'sales'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'related_acquisition', 
            'related_acquisition__ticket', # Access ticket details
            'agent', 
            'paid_to_account'
        ).order_by('-sale_date', '-created_at')
        
        filter_period = self.request.GET.get('filter_period', None)
        date_filter_str = self.request.GET.get('date_filter', None)
        start_date_str = self.request.GET.get('start_date', None)
        end_date_str = self.request.GET.get('end_date', None)

        today = timezone.localdate()
        target_date = today # Default to today

        if filter_period == 'day':
            if date_filter_str:
                try:
                    target_date = date.fromisoformat(date_filter_str)
                except ValueError:
                    messages.error(self.request, "Kiritilgan sana formati noto'g'ri.")
                    # Fallback to today or handle error appropriately, here defaulting to target_date = today
            queryset = queryset.filter(sale_date__date=target_date)
        elif filter_period == 'week':
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            queryset = queryset.filter(sale_date__date__range=[start_of_week, end_of_week])
        elif filter_period == 'month':
            start_of_month = today.replace(day=1)
            if today.month == 12:
                end_of_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_of_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
            queryset = queryset.filter(sale_date__date__range=[start_of_month, end_of_month])
        elif filter_period == 'custom' and start_date_str and end_date_str:
            try:
                start_date = date.fromisoformat(start_date_str)
                end_date = date.fromisoformat(end_date_str)
                if start_date <= end_date:
                    queryset = queryset.filter(sale_date__date__range=[start_date, end_date])
                else:
                    messages.error(self.request, "Boshlanish sanasi tugash sanasidan keyin bo'lishi mumkin emas.")
            except ValueError:
                messages.error(self.request, "Oraliq uchun kiritilgan sana formati noto'g'ri.")
        elif not filter_period: # Explicitly handle no filter_period (default to today)
            queryset = queryset.filter(sale_date__date=target_date)
        # If filter_period is something else, it won't apply date filtering, showing all sales.
        # Consider if this is desired, or if an error/default should apply.
        # For now, if filter_period is an unknown value, no date filter is applied from here.

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'sale_form' not in context:
            context['sale_form'] = SaleForm()
        
        context['current_filter_period'] = self.request.GET.get('filter_period', '')
        # Default to today's date for the single date filter input
        context['current_date_filter'] = self.request.GET.get('date_filter', timezone.localdate().isoformat() if not self.request.GET.get('filter_period') else self.request.GET.get('date_filter', ''))
        context['current_start_date'] = self.request.GET.get('start_date', '')
        context['current_end_date'] = self.request.GET.get('end_date', '')
        
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            del query_params['page']
        context['query_params'] = query_params.urlencode()

        # Calculate totals from the paginated queryset (self.object_list which is set by ListView)
        # If you need totals for the *entire* filtered set, not just the current page:
        # you would use self.get_queryset() directly before pagination is applied.
        # For simplicity, let's assume totals for the current page is acceptable for now,
        # or if not, we'd recalculate on the full filtered_queryset.

        # Let's get the full filtered queryset for totals:
        filtered_sales_for_totals = self.get_queryset() 

        totals = filtered_sales_for_totals.aggregate(
            total_quantity=Sum('quantity'),
            total_sum_uzs=Sum(
                Case(When(sale_currency='UZS', then='total_sale_amount'), default=Value(0), output_field=DecimalField())
            ),
            total_sum_usd=Sum(
                Case(When(sale_currency='USD', then='total_sale_amount'), default=Value(0), output_field=DecimalField())
            ),
            total_profit_uzs=Sum(
                Case(When(sale_currency='UZS', then='profit'), default=Value(0), output_field=DecimalField())
            ),
            total_profit_usd=Sum(
                Case(When(sale_currency='USD', then='profit'), default=Value(0), output_field=DecimalField())
            ),
            total_initial_payment_uzs=Sum(
                Case(When(agent__isnull=False, sale_currency='UZS', then='initial_payment_amount'), default=Value(0), output_field=DecimalField())
            ),
            total_initial_payment_usd=Sum(
                Case(When(agent__isnull=False, sale_currency='USD', then='initial_payment_amount'), default=Value(0), output_field=DecimalField())
            )
        )
        context['totals'] = totals
        
        return context

    def post(self, request, *args, **kwargs):
        form = SaleForm(request.POST)
        if form.is_valid():
            try:
                saved_sale = form.save() # The save method of Sale model handles stock and financial account updates
                messages.success(request, "Yangi sotuv muvaffaqiyatli qo'shildi.")
                return redirect(reverse_lazy('sales:sale-list')) 
            except ValidationError as e: # Catch validation errors from model's clean/save
                messages.error(request, f"Sotuvni saqlashda xatolik: {e}")
            except Exception as e:
                messages.error(request, f"Kutilmagan xatolik yuz berdi: {e}")
        else:
            # Existing code to re-render form follows
            pass # Pass if form is invalid, errors will be in form.errors
        
        self.object_list = self.get_queryset()
        context = self.get_context_data(sale_form=form, object_list=self.object_list)
        # Ensure error messages from the form are displayed, or add a generic one
        if not messages.get_messages(request):
             messages.error(request, "Sotuvni qo'shishda xatolik. Iltimos, ma'lumotlarni tekshiring.")
        return self.render_to_response(context)

def get_accounts_for_acquisition_currency(request, acquisition_id):
    try:
        acquisition = Acquisition.objects.get(pk=acquisition_id)
        currency = acquisition.transaction_currency
        accounts = FinancialAccount.objects.filter(currency=currency, is_active=True).values('id', 'name')
        return JsonResponse(list(accounts), safe=False)
    except Acquisition.DoesNotExist:
        return JsonResponse({'error': 'Acquisition not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
