from django.shortcuts import render
from django.views.generic import ListView
from .models import Acquisition

class AcquisitionListView(ListView):
    model = Acquisition
    template_name = 'inventory/acquisition_list.html' # We'll create this template next
    context_object_name = 'acquisitions'
    paginate_by = 20 # Optional: adds pagination

    def get_queryset(self):
        return Acquisition.objects.select_related('supplier', 'ticket', 'paid_from_account').order_by('-acquisition_date', '-created_at')

# Optional: Add a simple function-based view if you prefer for simple lists
# def acquisition_list_view(request):
#     acquisitions = Acquisition.objects.select_related('supplier', 'ticket', 'paid_from_account').order_by('-acquisition_date', '-created_at')
#     return render(request, 'inventory/acquisition_list.html', {'acquisitions': acquisitions})
