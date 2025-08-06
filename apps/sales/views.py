from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from django.http import JsonResponse
from django.db.models import Q, Sum
from django.core.paginator import Paginator
from django.contrib import messages

from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView
from django.core.exceptions import ValidationError

from .models import Sale, TicketReturn
from .forms import SaleForm, TicketReturnForm
from .services import SaleService, TicketReturnService
from apps.inventory.models import Acquisition
from apps.accounting.models import FinancialAccount
from apps.contacts.models import Agent, Supplier
from apps.core.services import DateFilterService


class SaleListView(LoginRequiredMixin, ListView):
    model = Sale
    template_name = 'sales/sale_list.html'
    context_object_name = 'sales'
    paginate_by = 20

    def get_queryset(self):
        queryset = Sale.objects.select_related(
            'related_acquisition__ticket',
            'related_acquisition__supplier',
            'agent',
            'salesperson',
            'paid_to_account'
        ).prefetch_related('returns').order_by('-sale_date', '-created_at')

        # Filter by salesperson if not superuser
        # Temporarily allow all sales for testing return functionality
        # if not self.request.user.is_superuser:
        #     queryset = queryset.filter(salesperson__user=self.request.user)

        # Apply filters
        queryset = self.apply_filters(queryset)
        return queryset

    def post(self, request, *args, **kwargs):
        """Handle sale creation via modal form"""
        form = SaleForm(request.POST, current_user=request.user)
        
        if form.is_valid():
            try:
                SaleService.create_sale(form)
                messages.success(request, "Sotuv muvaffaqiyatli qo'shildi.")
                return redirect('sales:sale-list')
            except ValidationError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, "Sotuvni qo'shishda xatolik yuz berdi.")
        else:
            # Store form errors for display in modal
            request.session['sale_form_errors'] = form.errors
            request.session['sale_form_data'] = request.POST
        
        return redirect('sales:sale-list')

    def apply_filters(self, queryset):
        # Agent filter
        agent_id = self.request.GET.get('agent')
        if agent_id:
            if agent_id == 'none':
                queryset = queryset.filter(agent__isnull=True)
            else:
                queryset = queryset.filter(agent_id=agent_id)

        # Currency filter
        currency = self.request.GET.get('currency')
        if currency:
            queryset = queryset.filter(sale_currency=currency)

        # Date range filter
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date or end_date:
            start_date_obj, end_date_obj = DateFilterService.get_date_range(
                'custom', None, start_date, end_date
            )
            queryset = queryset.filter(sale_date__date__range=[start_date_obj, end_date_obj])

        # Search filter
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(client_full_name__icontains=search) |
                Q(related_acquisition__ticket__description__icontains=search) |
                Q(agent__name__icontains=search) |
                Q(related_acquisition__supplier__name__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter options
        context['agents'] = Agent.objects.all().order_by('name')
        context['currencies'] = Sale.SaleCurrency.choices
        
        # Add additional filter options
        from apps.core.models import Salesperson
        context['salespeople'] = Salesperson.objects.select_related('user').all().order_by('user__first_name', 'user__last_name')
        context['suppliers'] = Supplier.objects.all().order_by('name')
        
        # Add sale form for modal
        if self.request.method == 'POST':
            # Use POST data if available
            context['sale_form'] = SaleForm(self.request.POST, current_user=self.request.user)
        else:
            # Check for form errors in session
            form_errors = self.request.session.pop('sale_form_errors', None)
            form_data = self.request.session.pop('sale_form_data', None)
            
            if form_errors and form_data:
                context['sale_form'] = SaleForm(form_data, current_user=self.request.user)
                context['sale_form'].errors = form_errors
            else:
                context['sale_form'] = SaleForm(current_user=self.request.user)
        
        # Add filter values for form persistence
        context['current_filters'] = {
            'agent': self.request.GET.get('agent'),
            'currency': self.request.GET.get('currency'),
            'start_date': self.request.GET.get('start_date'),
            'end_date': self.request.GET.get('end_date'),
            'search': self.request.GET.get('search'),
        }
        
        # Add individual filter values for template
        context['current_agent_filter'] = self.request.GET.get('agent')
        context['current_salesperson_filter'] = self.request.GET.get('salesperson')
        context['current_supplier_filter'] = self.request.GET.get('supplier')
        context['current_start_date'] = self.request.GET.get('start_date')
        context['current_end_date'] = self.request.GET.get('end_date')
        context['current_date_filter'] = self.request.GET.get('date_filter')
        
        # Build query params for pagination
        query_params = []
        for key, value in context['current_filters'].items():
            if value:
                query_params.append(f"{key}={value}")
        context['query_params'] = '&'.join(query_params)
        
        return context


@login_required
def get_accounts_for_acquisition_currency(request):
    """Get accounts filtered by currency"""
    try:
        currency = request.GET.get('currency')
        print(f"API called with currency: {currency}")
        
        if not currency:
            print("No currency provided")
            return JsonResponse({'error': 'Currency required'}, status=400)
        
        accounts = FinancialAccount.objects.filter(
            currency=currency
        ).order_by('name')
        
        print(f"Query: {accounts.query}")
        print(f"Found {accounts.count()} accounts for currency {currency}")
        
        account_list = [{'id': acc.id, 'name': acc.name} for acc in accounts]
        print(f"Account list: {account_list}")
        
        response_data = {'accounts': account_list}
        print(f"Returning: {response_data}")
        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"Exception in get_accounts_for_acquisition_currency: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def get_sale_info(request):
    """Get sale information for return form"""
    try:
        sale_id = request.GET.get('sale_id')
        if not sale_id:
            return JsonResponse({'error': 'Sale ID required'}, status=400)
        
        sale = get_object_or_404(Sale, pk=sale_id)
        
        sale_data = {
            'id': sale.id,
            'ticket_description': sale.related_acquisition.ticket.description,
            'supplier_name': sale.related_acquisition.supplier.name,
            'quantity': sale.quantity,
            'remaining_quantity': sale.remaining_quantity,
            'unit_price': sale.unit_sale_price,
            'total_amount': sale.total_sale_amount,
            'currency': sale.sale_currency,
            'buyer': sale.agent.name if sale.agent else sale.client_full_name,
            'salesperson': sale.salesperson.user.get_full_name() if sale.salesperson else 'N/A',
        }
        
        return JsonResponse({'sale': sale_data})
        
    except Sale.DoesNotExist:
        return JsonResponse({'error': 'Sale not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


class TicketReturnListView(LoginRequiredMixin, ListView):
    model = TicketReturn
    template_name = 'sales/return_list.html'
    context_object_name = 'returns'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = TicketReturn.objects.select_related(
            'original_sale__agent', 
            'original_sale__related_acquisition__ticket',
            'original_sale__related_acquisition__supplier',
            'fine_paid_to_account'
        ).order_by('-return_date')
        
        # Filter by salesperson if not superuser
        # Temporarily allow all returns for testing
        # if not self.request.user.is_superuser:
        #     queryset = queryset.filter(original_sale__salesperson__user=self.request.user)
        
        # Apply filters
        queryset = self.apply_filters(queryset)
        return queryset
    
    def apply_filters(self, queryset):
        # Agent filter
        agent_id = self.request.GET.get('agent')
        if agent_id:
            if agent_id == 'none':
                queryset = queryset.filter(original_sale__agent__isnull=True)
            else:
                queryset = queryset.filter(original_sale__agent_id=agent_id)
        
        # Currency filter
        currency = self.request.GET.get('currency')
        if currency:
            queryset = queryset.filter(fine_currency=currency)
        
        # Date range filter
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date or end_date:
            start_date_obj, end_date_obj = DateFilterService.get_date_range(
                'custom', None, start_date, end_date
            )
            queryset = queryset.filter(return_date__date__range=[start_date_obj, end_date_obj])
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter options
        context['agents'] = Agent.objects.all().order_by('name')
        context['currencies'] = Sale.SaleCurrency.choices
        
        # Add filter values for form persistence
        context['current_filters'] = {
            'agent': self.request.GET.get('agent'),
            'currency': self.request.GET.get('currency'),
            'start_date': self.request.GET.get('start_date'),
            'end_date': self.request.GET.get('end_date'),
        }
        
        # Build query params for pagination
        query_params = []
        for key, value in context['current_filters'].items():
            if value:
                query_params.append(f"{key}={value}")
        context['query_params'] = '&'.join(query_params)
        
        return context


class TicketReturnCreateView(LoginRequiredMixin, CreateView):
    model = TicketReturn
    form_class = TicketReturnForm
    template_name = 'sales/return_form.html'
    success_url = reverse_lazy('sales:return_list')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        
        return form
    
    def form_valid(self, form):
        try:
            print("Form is valid, creating return...")
            form.instance = TicketReturnService.create_return(form, self.request.user)
            messages.success(self.request, "Chipta qaytarishi muvaffaqiyatli yaratildi.")
            return super().form_valid(form)
        except ValidationError as e:
            print(f"Validation error: {e}")
            messages.error(self.request, str(e))
            return self.form_invalid(form)
        except Exception as e:
            print(f"Exception: {e}")
            messages.error(self.request, f"Xatolik yuz berdi: {str(e)}")
            return self.form_invalid(form)


class TicketReturnDetailView(LoginRequiredMixin, DetailView):
    model = TicketReturn
    template_name = 'sales/return_detail.html'
    context_object_name = 'return_instance'
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'original_sale__agent',
            'original_sale__related_acquisition__ticket',
            'original_sale__related_acquisition__supplier',
            'fine_paid_to_account'
        )
        
        # Filter by salesperson if not superuser
        # Temporarily allow all returns for testing
        # if not self.request.user.is_superuser:
        #     queryset = queryset.filter(original_sale__salesperson__user=self.request.user)
        
        return queryset


