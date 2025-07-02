from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import ListView
from django.http import HttpResponse
from .models import Acquisition, Ticket
from .forms import AcquisitionForm
from apps.core.services import DateFilterService
from apps.contacts.models import SupplierPayment
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter
import logging

logger = logging.getLogger(__name__)


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
        except ValueError as e:
            logger.warning(f"Date filter error: {e}")
            # Fall back to today's data on error
            today = timezone.localdate()
            queryset = queryset.filter(acquisition_date__date=today)
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = AcquisitionForm()
        return context

    def post(self, request, *args, **kwargs):
        """Handle acquisition creation with ticket and business logic"""
        form = AcquisitionForm(request.POST)
        if form.is_valid():
            try:
                # Create ticket first
                ticket = Ticket.objects.create(
                    ticket_type=form.cleaned_data['ticket_type'],
                    description=form.cleaned_data['ticket_description'],
                    departure_date_time=form.cleaned_data['ticket_departure_date_time'],
                    arrival_date_time=form.cleaned_data.get('ticket_arrival_date_time')
                )
                
                # Create acquisition
                acquisition = form.save(commit=False)
                acquisition.ticket = ticket
                acquisition.save()
                
                # Handle business logic moved from model
                # Step 1: Always add debt to supplier
                acquisition.supplier.add_debt(acquisition.total_amount, acquisition.currency)
                
                # Step 2: If automatic payment, create payment record
                if acquisition.paid_from_account:
                    SupplierPayment.objects.create(
                        supplier=acquisition.supplier,
                        payment_date=acquisition.acquisition_date,
                        amount=acquisition.total_amount,
                        currency=acquisition.currency,
                        paid_from_account=acquisition.paid_from_account,
                        notes=f"Avtomatik to'lov - Xarid #{acquisition.pk}"
                    )
                
                logger.info(f"Created acquisition {acquisition.id}")
                return redirect(reverse_lazy('inventory:acquisition-list'))
                
            except Exception as e:
                logger.error(f"Error creating acquisition: {e}")
        else:
            logger.warning(f"Form validation failed: {form.errors}")

        return redirect(reverse_lazy('inventory:acquisition-list'))

    def export_to_excel(self, request):
        """Export filtered acquisitions to Excel"""
        acquisitions = self._get_filtered_queryset()
        
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Xaridlar Ro'yxati"
        
        headers = [
            'Sana', 'Ta\'minotchi', 'Chipta Turi', 'Tavsif', 
            'Miqdor', 'Narxi', 'Jami Summa', 'To\'lov Holati'
        ]
        
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        
        for col_num, header in enumerate(headers, 1):
            cell = worksheet.cell(row=1, column=col_num)
            cell.value = header
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")
        
        for row_num, acq in enumerate(acquisitions, 2):
            worksheet.cell(row=row_num, column=1, value=acq.acquisition_date.strftime('%d.%m.%Y'))
            worksheet.cell(row=row_num, column=2, value=acq.supplier.name)
            worksheet.cell(row=row_num, column=3, value=acq.ticket.get_ticket_type_display())
            worksheet.cell(row=row_num, column=4, value=acq.ticket.description)
            worksheet.cell(row=row_num, column=5, value=f"{acq.available_quantity}/{acq.initial_quantity}")
            worksheet.cell(row=row_num, column=6, value=f"{acq.unit_price} {acq.currency}")
            worksheet.cell(row=row_num, column=7, value=f"{acq.total_amount} {acq.currency}")
            worksheet.cell(row=row_num, column=8, value="To'langan" if acq.paid_from_account else "To'lanmagan")
        
        for column in worksheet.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
        
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="xaridlar_royxati.xlsx"'
        workbook.save(response)
        return response