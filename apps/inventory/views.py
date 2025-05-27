from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView
from django.contrib import messages
from .models import Acquisition
from .forms import AcquisitionForm # Import the new form
from django.utils import timezone
from datetime import timedelta, date

class AcquisitionListView(ListView):
    model = Acquisition
    template_name = 'inventory/acquisition_list.html' # We'll create this template next
    context_object_name = 'acquisitions'
    paginate_by = 20 # Optional: adds pagination

    def get_queryset(self):
        queryset = super().get_queryset().select_related('supplier', 'ticket', 'paid_from_account').order_by('-acquisition_date', '-created_at')
        
        filter_period = self.request.GET.get('filter_period', None)
        date_filter_str = self.request.GET.get('date_filter', None)
        start_date_str = self.request.GET.get('start_date', None)
        end_date_str = self.request.GET.get('end_date', None)

        today = timezone.localdate()

        if filter_period == 'day':
            if date_filter_str:
                try:
                    selected_date = date.fromisoformat(date_filter_str)
                    queryset = queryset.filter(acquisition_date=selected_date)
                except ValueError:
                    messages.error(self.request, "Kiritilgan sana formati noto'g'ri.")
            else: # Default to today if no specific date is provided for 'day' filter
                queryset = queryset.filter(acquisition_date=today)
        elif filter_period == 'week':
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            queryset = queryset.filter(acquisition_date__range=[start_of_week, end_of_week])
        elif filter_period == 'month':
            start_of_month = today.replace(day=1)
            # To get the end of the month, go to the first day of the next month and subtract one day
            if today.month == 12:
                end_of_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_of_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
            queryset = queryset.filter(acquisition_date__range=[start_of_month, end_of_month])
        elif filter_period == 'custom' and start_date_str and end_date_str:
            try:
                start_date = date.fromisoformat(start_date_str)
                end_date = date.fromisoformat(end_date_str)
                if start_date <= end_date:
                    queryset = queryset.filter(acquisition_date__range=[start_date, end_date])
                else:
                    messages.error(self.request, "Boshlanish sanasi tugash sanasidan keyin bo'lishi mumkin emas.")
            except ValueError:
                messages.error(self.request, "Oraliq uchun kiritilgan sana formati noto'g'ri.")
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add form to context if not already there (e.g. from a failed POST)
        if 'acquisition_form' not in context:
            context['acquisition_form'] = AcquisitionForm()
        
        context['current_filter_period'] = self.request.GET.get('filter_period', '')
        context['current_date_filter'] = self.request.GET.get('date_filter', timezone.localdate().isoformat())
        context['current_start_date'] = self.request.GET.get('start_date', '')
        context['current_end_date'] = self.request.GET.get('end_date', '')
        
        # For building query strings in pagination, preserving filters
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            del query_params['page']
        context['query_params'] = query_params.urlencode()
        return context

    def post(self, request, *args, **kwargs):
        form = AcquisitionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Yangi xarid muvaffaqiyatli qo'shildi.")
            return redirect(reverse_lazy('inventory:acquisition-list')) # Redirect to GET to avoid re-post
        else:
            # If form is invalid, re-render the page with the form and errors
            # We need to call get_queryset and paginate again for the ListView context
            self.object_list = self.get_queryset() # Important for ListView
            context = self.get_context_data(acquisition_form=form, object_list=self.object_list)
            messages.error(request, "Xaridni qo'shishda xatolik. Iltimos, ma'lumotlarni tekshiring.")
            return self.render_to_response(context)

# Optional: Add a simple function-based view if you prefer for simple lists
# def acquisition_list_view(request):
#     acquisitions = Acquisition.objects.select_related('supplier', 'ticket', 'paid_from_account').order_by('-acquisition_date', '-created_at')
#     return render(request, 'inventory/acquisition_list.html', {'acquisitions': acquisitions})
