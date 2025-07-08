from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import ListView
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import Sale
from .forms import SaleForm
from .services import SaleService
from .utils import calculate_sales_totals
from apps.inventory.models import Acquisition
from apps.accounting.models import FinancialAccount
from apps.core.models import Salesperson
from apps.core.services import DateFilterService


class SaleListView(LoginRequiredMixin, ListView):
    model = Sale
    template_name = 'sales/sale_list.html'
    context_object_name = 'sales'
    paginate_by = 20
    login_url = '/core/login/'

    def get_queryset(self):
        """Get filtered queryset with optimized queries"""
        queryset = self.model.objects.select_related(
            'related_acquisition', 
            'related_acquisition__ticket',
            'agent', 
            'paid_to_account',
            'salesperson',
            'salesperson__user'
        ).order_by('-sale_date', '-created_at')
        
        # Filter by current salesperson
        try:
            current_salesperson = self.request.user.salesperson_profile
            queryset = queryset.filter(salesperson=current_salesperson)
        except Salesperson.DoesNotExist:
            if not self.request.user.is_superuser:
                queryset = queryset.none()
        
        # Apply date filtering
        try:
            start_date, end_date = DateFilterService.get_date_range(
                self.request.GET.get('filter_period'),
                self.request.GET.get('date_filter'),
                self.request.GET.get('start_date'),
                self.request.GET.get('end_date')
            )
            queryset = queryset.filter(sale_date__date__range=[start_date, end_date])
        except ValueError:
            today = timezone.localdate()
            queryset = queryset.filter(sale_date__date=today)
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if 'sale_form' not in context:
            context['sale_form'] = SaleForm(current_user=self.request.user)
        
        # Get filter context
        filter_context = DateFilterService.get_filter_context(
            self.request.GET.get('filter_period'),
            self.request.GET.get('date_filter'),
            self.request.GET.get('start_date'),
            self.request.GET.get('end_date')
        )
        context.update(filter_context)

        # Calculate totals
        context['totals'] = calculate_sales_totals(self.get_queryset())
        
        # Preserve query parameters
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            del query_params['page']
        context['query_params'] = query_params.urlencode()
        
        return context



    def post(self, request, *args, **kwargs):
        """Handle sale creation"""
        form = SaleForm(request.POST, current_user=request.user)
        if form.is_valid():
            try:
                sale = SaleService.create_sale(form)
                if sale:
                    return redirect(reverse_lazy('sales:sale-list'))
            except (ValidationError, Exception):
                pass

        # Re-render with form errors
        self.object_list = self.get_queryset()
        context = self.get_context_data(sale_form=form, object_list=self.object_list)
        
        return self.render_to_response(context)


@login_required(login_url='/core/login/')
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
        return JsonResponse({'error': str(e)}, status=500)