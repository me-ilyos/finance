from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView
from django.contrib import messages
from .models import Acquisition
from .forms import AcquisitionForm
from .services import AcquisitionService
from django.utils import timezone
from datetime import timedelta, date
import logging

logger = logging.getLogger(__name__)


class AcquisitionListView(ListView):
    model = Acquisition
    template_name = 'inventory/acquisition_list.html'
    context_object_name = 'acquisitions'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related('supplier', 'ticket', 'paid_from_account').order_by('-acquisition_date', '-created_at')
        
        # Store filter parameters for context
        self.filter_period = self.request.GET.get('filter_period')
        self.date_filter = self.request.GET.get('date_filter')
        self.start_date = self.request.GET.get('start_date')
        self.end_date = self.request.GET.get('end_date')

        today = timezone.localdate()

        if self.filter_period == 'day':
            if self.date_filter:
                try:
                    selected_date = date.fromisoformat(self.date_filter)
                    queryset = queryset.filter(acquisition_date__date=selected_date)
                except ValueError:
                    messages.error(self.request, "Kiritilgan sana formati noto'g'ri.")
            else:
                queryset = queryset.filter(acquisition_date__date=today)
        elif self.filter_period == 'week':
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            queryset = queryset.filter(acquisition_date__date__range=[start_of_week, end_of_week])
        elif self.filter_period == 'month':
            start_of_month = today.replace(day=1)
            if today.month == 12:
                end_of_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_of_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
            queryset = queryset.filter(acquisition_date__date__range=[start_of_month, end_of_month])
        elif self.filter_period == 'custom' and self.start_date and self.end_date:
            try:
                start_date = date.fromisoformat(self.start_date)
                end_date = date.fromisoformat(self.end_date)
                if start_date <= end_date:
                    queryset = queryset.filter(acquisition_date__date__range=[start_date, end_date])
                else:
                    messages.error(self.request, "Boshlanish sanasi tugash sanasidan keyin bo'lishi mumkin emas.")
            except ValueError:
                messages.error(self.request, "Oraliq uchun kiritilgan sana formati noto'g'ri.")
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add form to context if not already there
        if 'acquisition_form' not in context:
            context['acquisition_form'] = AcquisitionForm()
        
        context['current_filter_period'] = self.filter_period or ''
        context['current_date_filter'] = self.date_filter or timezone.localdate().isoformat()
        context['current_start_date'] = self.start_date or ''
        context['current_end_date'] = self.end_date or ''
        
        # For building query strings in pagination, preserving filters
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            del query_params['page']
        context['query_params'] = query_params.urlencode()
        return context

    def post(self, request, *args, **kwargs):
        """Handle acquisition creation using service layer"""
        form = AcquisitionForm(request.POST)
        if form.is_valid():
            try:
                acquisition = form.save()
                if acquisition:
                    messages.success(request, "Yangi xarid muvaffaqiyatli qo'shildi.")
                    return redirect(reverse_lazy('inventory:acquisition-list'))
                else:
                    messages.error(request, "Xaridni saqlashda xatolik yuz berdi.")
            except Exception as e:
                logger.error(f"Error creating acquisition: {e}")
                messages.error(request, "Xaridni yaratishda kutilmagan xatolik yuz berdi.")
        else:
            # If form is invalid, re-render the page with the form and errors
            self.object_list = self.get_queryset()
            context = self.get_context_data(acquisition_form=form, object_list=self.object_list)
            messages.error(request, "Xaridni qo'shishda xatolik. Iltimos, ma'lumotlarni tekshiring.")
            return self.render_to_response(context)