from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView
from django.http import HttpResponse
from .models import Acquisition
from .forms import AcquisitionForm
from apps.core.services import DateFilterService
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


def export_acquisitions_excel(request):
    """Export acquisitions data to Excel (XLSX) format"""
    try:
        # Get the same queryset as the list view
        queryset = Acquisition.objects.select_related(
            'supplier', 'ticket', 'paid_from_account'
        ).order_by('-acquisition_date', '-created_at')
        
        # Apply the same filtering as the list view
        filter_period = request.GET.get('filter_period')
        date_filter = request.GET.get('date_filter')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        try:
            start_date_obj, end_date_obj = DateFilterService.get_date_range(
                filter_period, date_filter, start_date, end_date
            )
            queryset = queryset.filter(acquisition_date__date__range=[start_date_obj, end_date_obj])
        except ValueError:
            # Fall back to today's data on error
            today = timezone.localdate()
            queryset = queryset.filter(acquisition_date__date=today)

        # Create Excel workbook and worksheet
        wb = Workbook()
        ws = wb.active
        ws.title = "Xaridlar Ro'yxati"

        # Define headers (matching the table structure)
        headers = [
            'Sana',
            'Ta\'minotchi',
            'Chipta turi', 
            'Chipta manzili',
            'Mavjud miqdori',
            'Boshlang\'ich miqdori',
            'Birlik narxi',
            'Jami summa',
            'Valyuta',
            'To\'lov hisobi',
            'To\'lov holati',
            'Izohlar'
        ]

        # Write headers
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num, value=header)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            cell.alignment = Alignment(horizontal="center", vertical="center")

        # Write data rows
        for row_num, acquisition in enumerate(queryset, 2):
            # Format data to match template display
            acquisition_date = acquisition.acquisition_date.strftime('%d.%m.%Y')
            supplier_name = acquisition.supplier.name
            ticket_type = acquisition.ticket.get_ticket_type_display()
            ticket_description = acquisition.ticket.description
            available_quantity = acquisition.available_quantity
            initial_quantity = acquisition.initial_quantity
            
            # Format price and total based on currency
            if acquisition.currency == 'UZS':
                unit_price = f"{acquisition.unit_price:,.0f}"
                total_amount = f"{acquisition.total_amount:,.0f}"
            else:  # USD
                unit_price = f"{acquisition.unit_price:,.2f}"
                total_amount = f"{acquisition.total_amount:,.2f}"
            
            currency = acquisition.currency
            payment_account = acquisition.paid_from_account.name if acquisition.paid_from_account else "To'lanmagan"
            payment_status = "To'langan" if acquisition.paid_from_account else "To'lanmagan"
            notes = acquisition.notes or ""

            # Write row data
            row_data = [
                acquisition_date,
                supplier_name,
                ticket_type,
                ticket_description,
                available_quantity,
                initial_quantity,
                unit_price,
                total_amount,
                currency,
                payment_account,
                payment_status,
                notes
            ]

            for col_num, value in enumerate(row_data, 1):
                cell = ws.cell(row=row_num, column=col_num, value=value)
                
                # Center align numeric columns
                if col_num in [5, 6, 7, 8]:  # quantity and price columns
                    cell.alignment = Alignment(horizontal="center")
                elif col_num in [9, 10, 11]:  # currency, account, status columns
                    cell.alignment = Alignment(horizontal="center")

        # Auto-adjust column widths
        for column in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            
            # Set minimum and maximum width limits
            adjusted_width = min(max(max_length + 2, 12), 50)
            ws.column_dimensions[column_letter].width = adjusted_width

        # Create HTTP response with Excel file
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        # Set filename based on filter
        if start_date_obj and end_date_obj:
            if start_date_obj == end_date_obj:
                filename = f"xaridlar_{start_date_obj.strftime('%d.%m.%Y')}.xlsx"
            else:
                filename = f"xaridlar_{start_date_obj.strftime('%d.%m.%Y')}_dan_{end_date_obj.strftime('%d.%m.%Y')}_gacha.xlsx"
        else:
            filename = f"xaridlar_{timezone.now().strftime('%d.%m.%Y')}.xlsx"
            
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        # Save workbook to response
        wb.save(response)
        
        logger.info(f"Exported {queryset.count()} acquisitions to Excel")
        return response

    except Exception as e:
        logger.error(f"Error exporting acquisitions to Excel: {e}")
        return HttpResponse("Excel export xatolik bilan yakunlandi.", status=500)