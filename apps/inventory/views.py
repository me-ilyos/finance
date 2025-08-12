from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import ListView
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Acquisition
from .forms import AcquisitionForm
from .services import AcquisitionService
from apps.core.services import DateFilterService
from apps.core.models import Salesperson
from apps.contacts.models import Supplier
from django.utils import timezone


class AcquisitionListView(ListView):
    model = Acquisition
    template_name = 'inventory/acquisition_list.html'
    context_object_name = 'acquisitions'
    paginate_by = 20

    def get_queryset(self):
        return self._get_filtered_queryset()

    def _get_filtered_queryset(self):
        """Centralized queryset filtering with optimized queries"""
        queryset = self.model.objects.filter(is_active=True).select_related(
            'supplier', 'ticket', 'paid_from_account', 'salesperson', 'salesperson__user'
        ).order_by('-acquisition_date', '-created_at')
        
        # Apply salesperson filtering based on user role
        if self.request.user.is_superuser:
            # Admin can see all acquisitions, but can filter by specific salesperson
            salesperson_filter = self.request.GET.get('salesperson')
            if salesperson_filter:
                try:
                    salesperson_id = int(salesperson_filter)
                    queryset = queryset.filter(salesperson_id=salesperson_id)
                except (ValueError, TypeError):
                    pass
        else:
            # Non-admin users only see their own acquisitions
            try:
                current_salesperson = self.request.user.salesperson_profile
                queryset = queryset.filter(salesperson=current_salesperson)
            except Salesperson.DoesNotExist:
                queryset = queryset.none()
        
        # Apply supplier filtering (admin only)
        if self.request.user.is_superuser:
            supplier_filter = self.request.GET.get('supplier')
            if supplier_filter:
                try:
                    supplier_id = int(supplier_filter)
                    queryset = queryset.filter(supplier_id=supplier_id)
                except (ValueError, TypeError):
                    pass
        
        # Apply date filtering
        try:
            # Prefer explicit inputs; fallback to preserved values from admin filter submit
            qd = self.request.GET
            # Canonical params only; front-end keeps URL clean
            filter_period = qd.get('filter_period')
            if filter_period == 'day':
                date_filter = qd.get('date_filter')
                start_date = None
                end_date = None
            elif filter_period == 'custom':
                date_filter = None
                start_date = qd.get('start_date')
                end_date = qd.get('end_date')
            else:
                date_filter = None
                start_date = None
                end_date = None

            start_date_obj, end_date_obj = DateFilterService.get_date_range(
                filter_period,
                date_filter,
                start_date,
                end_date
            )
            queryset = queryset.filter(acquisition_date__date__range=[start_date_obj, end_date_obj])
        except ValueError:
            # Fall back to today's data on error
            today = timezone.localdate()
            queryset = queryset.filter(acquisition_date__date=today)
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['acquisition_form'] = AcquisitionForm(current_user=self.request.user)
        
        # Add filter options for admin users
        if self.request.user.is_superuser:
            # Get salespeople for dropdown (optimized query)
            context['salespeople'] = Salesperson.objects.select_related('user').filter(
                is_active=True
            ).order_by('user__first_name', 'user__last_name')
            
            # Get suppliers for dropdown (optimized query)
            context['suppliers'] = Supplier.objects.filter(
                is_active=True
            ).order_by('name')
            
            # Add current filter values
            context['current_salesperson_filter'] = self.request.GET.get('salesperson', '')
            context['current_supplier_filter'] = self.request.GET.get('supplier', '')
        
        # Preserve query parameters for pagination
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            query_params.pop('page')
        context['query_params'] = query_params.urlencode()
        
        # Add current filter values for the form (use last values to reflect the user's latest intent)
        qd = self.request.GET
        context['current_filter_period'] = qd.get('filter_period')
        context['current_date_filter'] = qd.get('date_filter')
        context['current_start_date'] = qd.get('start_date')
        context['current_end_date'] = qd.get('end_date')
        
        return context

    def post(self, request, *args, **kwargs):
        """Handle acquisition creation using service layer"""
        form = AcquisitionForm(request.POST, current_user=request.user)
        if form.is_valid():
            try:
                AcquisitionService.create_acquisition(form)
                return redirect(reverse_lazy('inventory:acquisition-list'))
            except Exception:
                pass

        return redirect(reverse_lazy('inventory:acquisition-list'))



@login_required(login_url='/core/login/')
def api_acquisitions_list(request):
    """API endpoint to get list of available acquisitions for dropdowns - optimized queries"""
    queryset = Acquisition.objects.filter(
        available_quantity__gt=0, 
        is_active=True
    ).select_related(
        'ticket', 'supplier'
    )
    
    # Filter by current salesperson - only show acquisitions made by this salesperson
    try:
        current_salesperson = request.user.salesperson_profile
        queryset = queryset.filter(salesperson=current_salesperson)
    except Salesperson.DoesNotExist:
        # If user is not a salesperson but is superuser, show all acquisitions
        if not request.user.is_superuser:
            queryset = queryset.none()
    
    acquisitions = queryset.values(
        'id', 'ticket__description', 'available_quantity', 'currency', 
        'supplier__name', 'acquisition_date'
    ).order_by('-acquisition_date')
    
    # Format for display
    result = []
    for acq in acquisitions:
        currency_symbol = "UZS" if acq['currency'] == 'UZS' else "$"
        display_name = (f"{acq['acquisition_date'].strftime('%d.%m.%y')} - "
                       f"{acq['ticket__description'][:25]}... ({acq['available_quantity']} dona) - "
                       f"{currency_symbol} - {acq['supplier__name'][:15]}")
        result.append({
            'id': acq['id'],
            'display_name': display_name
        })
    
    return JsonResponse(result, safe=False)