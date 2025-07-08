from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import ListView
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Acquisition
from .forms import AcquisitionForm
from .services import AcquisitionService
from apps.core.services import DateFilterService
from django.utils import timezone


class AcquisitionListView(ListView):
    model = Acquisition
    template_name = 'inventory/acquisition_list.html'
    context_object_name = 'acquisitions'
    paginate_by = 20

    def get_queryset(self):
        return self._get_filtered_queryset()

    def _get_filtered_queryset(self):
        """Centralized queryset filtering to avoid duplication"""
        queryset = self.model.objects.select_related(
            'supplier', 'ticket', 'paid_from_account'
        ).order_by('-acquisition_date', '-created_at')
        
        # Apply date filtering
        try:
            start_date_obj, end_date_obj = DateFilterService.get_date_range(
                self.request.GET.get('filter_period'),
                self.request.GET.get('date_filter'),
                self.request.GET.get('start_date'),
                self.request.GET.get('end_date')
            )
            queryset = queryset.filter(acquisition_date__date__range=[start_date_obj, end_date_obj])
        except ValueError:
            # Fall back to today's data on error
            today = timezone.localdate()
            queryset = queryset.filter(acquisition_date__date=today)
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = AcquisitionForm()
        return context

    def post(self, request, *args, **kwargs):
        """Handle acquisition creation using service layer"""
        form = AcquisitionForm(request.POST)
        if form.is_valid():
            try:
                AcquisitionService.create_acquisition(form)
                return redirect(reverse_lazy('inventory:acquisition-list'))
            except Exception:
                pass

        return redirect(reverse_lazy('inventory:acquisition-list'))



@login_required(login_url='/core/login/')
def api_acquisitions_list(request):
    """API endpoint to get list of available acquisitions for dropdowns"""
    acquisitions = Acquisition.objects.filter(available_quantity__gt=0).select_related(
        'ticket', 'supplier'
    ).values(
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