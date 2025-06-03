from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView
from .models import Acquisition
from .forms import AcquisitionForm
from apps.core.services import DateFilterService
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class AcquisitionListView(ListView):
    model = Acquisition
    template_name = 'inventory/acquisition_list.html'
    context_object_name = 'acquisitions'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'supplier', 'ticket', 'paid_from_account'
        ).order_by('-acquisition_date', '-created_at')
        
        # Get filter parameters
        filter_period = self.request.GET.get('filter_period')
        date_filter = self.request.GET.get('date_filter')
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')

        # Use centralized date filtering service
        try:
            start_date_obj, end_date_obj = DateFilterService.get_date_range(
                filter_period, date_filter, start_date, end_date
            )
            queryset = queryset.filter(acquisition_date__date__range=[start_date_obj, end_date_obj])
        except ValueError as e:
            logger.warning(f"Date filter error: {e}")
            # Fall back to today's data on error
            today = timezone.localdate()
            queryset = queryset.filter(acquisition_date__date=today)
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add form to context
        if 'acquisition_form' not in context:
            context['acquisition_form'] = AcquisitionForm()
        
        # Use centralized filter context service
        filter_context = DateFilterService.get_filter_context(
            self.request.GET.get('filter_period'),
            self.request.GET.get('date_filter'),
            self.request.GET.get('start_date'),
            self.request.GET.get('end_date')
        )
        context.update(filter_context)
        
        # For pagination - preserve query parameters
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            del query_params['page']
        context['query_params'] = query_params.urlencode()
        
        return context

    def post(self, request, *args, **kwargs):
        """Handle acquisition creation"""
        form = AcquisitionForm(request.POST)
        if form.is_valid():
            try:
                acquisition = form.save()
                logger.info(f"Created acquisition {acquisition.id}")
                return redirect(reverse_lazy('inventory:acquisition-list'))
            except Exception as e:
                logger.error(f"Error creating acquisition: {e}")
        else:
            logger.warning(f"Form validation errors: {form.errors}")
        
        # Re-render with form errors
        self.object_list = self.get_queryset()
        context = self.get_context_data(acquisition_form=form, object_list=self.object_list)
        return self.render_to_response(context)