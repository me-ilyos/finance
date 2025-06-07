from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from .models import Sale
from .forms import SaleForm
from .services import SaleService
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal
from apps.inventory.models import Acquisition
from apps.accounting.models import FinancialAccount
from django.db.models import Sum, Case, When, Value, DecimalField
from django.core.exceptions import ValidationError
from apps.core.services import DateFilterService
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter
import logging

logger = logging.getLogger(__name__)


class SaleListView(ListView):
    model = Sale
    template_name = 'sales/sale_list.html'
    context_object_name = 'sales'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'related_acquisition', 
            'related_acquisition__ticket',
            'agent', 
            'paid_to_account'
        ).order_by('-sale_date', '-created_at')
        
        # Store filter parameters for context
        self.filter_period = self.request.GET.get('filter_period')
        self.date_filter = self.request.GET.get('date_filter')
        self.start_date = self.request.GET.get('start_date')
        self.end_date = self.request.GET.get('end_date')

        # Apply date filtering using service
        start_date, end_date = DateFilterService.get_date_range(
            self.filter_period, self.date_filter, self.start_date, self.end_date
        )
        
        return queryset.filter(sale_date__date__range=[start_date, end_date])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if 'sale_form' not in context:
            context['sale_form'] = SaleForm()
        
        # Use the service to get filter context
        filter_context = DateFilterService.get_filter_context(
            self.filter_period, self.date_filter, self.start_date, self.end_date
        )
        context.update(filter_context)

        # Calculate totals for the current filtered queryset
        filtered_queryset = self.get_queryset()
        totals = filtered_queryset.aggregate(
            total_quantity=Sum('quantity'),
            total_sum_uzs=Sum(
                Case(When(sale_currency='UZS', then='total_sale_amount'), 
                     default=Value(0), output_field=DecimalField())
            ),
            total_sum_usd=Sum(
                Case(When(sale_currency='USD', then='total_sale_amount'), 
                     default=Value(0), output_field=DecimalField())
            ),
            total_profit_uzs=Sum(
                Case(When(sale_currency='UZS', then='profit'), 
                     default=Value(0), output_field=DecimalField())
            ),
            total_profit_usd=Sum(
                Case(When(sale_currency='USD', then='profit'), 
                     default=Value(0), output_field=DecimalField())
            ),
            total_initial_payment_uzs=Sum(
                Case(When(agent__isnull=False, sale_currency='UZS', then='initial_payment_amount'), 
                     default=Value(0), output_field=DecimalField())
            ),
            total_initial_payment_usd=Sum(
                Case(When(agent__isnull=False, sale_currency='USD', then='initial_payment_amount'), 
                     default=Value(0), output_field=DecimalField())
            )
        )
        context['totals'] = totals
        
        # Preserve query parameters for pagination
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            del query_params['page']
        context['query_params'] = query_params.urlencode()
        
        return context

    def post(self, request, *args, **kwargs):
        """Handle sale creation using service layer"""
        form = SaleForm(request.POST)
        if form.is_valid():
            try:
                sale = form.save()
                if sale:
                    messages.success(request, "Yangi sotuv muvaffaqiyatli qo'shildi.")
                    return redirect(reverse_lazy('sales:sale-list'))
                else:
                    messages.error(request, "Sotuvni saqlashda xatolik yuz berdi.")
            except ValidationError as e:
                logger.error(f"Validation error creating sale: {e}")
                messages.error(request, f"Sotuvni saqlashda xatolik: {e}")
            except Exception as e:
                logger.error(f"Unexpected error creating sale: {e}")
                messages.error(request, "Kutilmagan xatolik yuz berdi.")
        else:
            logger.warning(f"Invalid form data: {form.errors}")

        # Re-render with form errors
        self.object_list = self.get_queryset()
        context = self.get_context_data(sale_form=form, object_list=self.object_list)
        
        if not messages.get_messages(request):
            messages.error(request, "Sotuvni qo'shishda xatolik. Iltimos, ma'lumotlarni tekshiring.")
        
        return self.render_to_response(context)


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
        logger.error(f"Error in get_accounts_for_acquisition_currency: {e}")
        return JsonResponse({'error': str(e)}, status=500)


def export_sales_excel(request):
    """Export sales data to Excel (XLSX) format"""
    try:
        # Get the same queryset as the list view
        queryset = Sale.objects.select_related(
            'related_acquisition', 
            'related_acquisition__ticket',
            'agent', 
            'paid_to_account'
        ).order_by('-sale_date', '-created_at')
        
        # Apply the same filtering as the list view
        filter_period = request.GET.get('filter_period')
        date_filter = request.GET.get('date_filter')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        try:
            start_date_obj, end_date_obj = DateFilterService.get_date_range(
                filter_period, date_filter, start_date, end_date
            )
            queryset = queryset.filter(sale_date__date__range=[start_date_obj, end_date_obj])
        except ValueError:
            # Fall back to today's data on error
            today = timezone.localdate()
            queryset = queryset.filter(sale_date__date=today)

        # Create Excel workbook and worksheet
        wb = Workbook()
        ws = wb.active
        ws.title = "Sotuvlar Ro'yxati"

        # Define headers (matching the table structure)
        headers = [
            'Sana',
            'Chipta turi',
            'Chipta manzili', 
            'Xaridor',
            'Miqdori',
            'Birlik narxi',
            'Jami summa',
            'Valyuta',
            'Foyda',
            'Boshlang\'ich to\'lov',
            'To\'lov hisobi',
            'To\'lov holati',
            'Agent'
        ]

        # Write headers
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num, value=header)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            cell.alignment = Alignment(horizontal="center", vertical="center")

        # Write data rows
        for row_num, sale in enumerate(queryset, 2):
            # Format data to match template display
            sale_date = sale.sale_date.strftime('%d.%m.%Y %H:%M')
            ticket_type = sale.related_acquisition.ticket.get_ticket_type_display()
            ticket_description = sale.related_acquisition.ticket.description
            
            # Buyer display
            if sale.agent:
                buyer = sale.agent.name
                agent_name = sale.agent.name
            else:
                buyer = sale.client_full_name or "N/A"
                agent_name = ""
            
            quantity = sale.quantity
            
            # Format prices based on currency
            currency = sale.sale_currency
            if currency == 'UZS':
                unit_price = f"{sale.unit_sale_price:,.0f}"
                total_amount = f"{sale.total_sale_amount:,.0f}"
                profit = f"{sale.profit:,.0f}"
                initial_payment = f"{sale.initial_payment_amount:,.0f}" if sale.initial_payment_amount else ""
            else:  # USD
                unit_price = f"{sale.unit_sale_price:,.2f}"
                total_amount = f"{sale.total_sale_amount:,.2f}"
                profit = f"{sale.profit:,.2f}"
                initial_payment = f"{sale.initial_payment_amount:,.2f}" if sale.initial_payment_amount else ""
            
            # Payment status
            if sale.agent:
                if sale.initial_payment_amount:
                    payment_status = f"Agent qarzi (boshlang'ich: {initial_payment} {currency})"
                else:
                    payment_status = "Agent qarzi"
                payment_account = ""
            elif sale.paid_to_account:
                payment_status = "To'langan"
                payment_account = sale.paid_to_account.name
            else:
                payment_status = "To'lanmagan"
                payment_account = ""

            # Write row data
            row_data = [
                sale_date,
                ticket_type,
                ticket_description,
                buyer,
                quantity,
                unit_price,
                total_amount,
                currency,
                profit,
                initial_payment,
                payment_account,
                payment_status,
                agent_name
            ]

            for col_num, value in enumerate(row_data, 1):
                cell = ws.cell(row=row_num, column=col_num, value=value)
                
                # Center align numeric and status columns
                if col_num in [5, 6, 7, 8, 9, 10]:  # quantity, prices, profit columns
                    cell.alignment = Alignment(horizontal="center")
                elif col_num in [11, 12]:  # payment account, status columns
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
                filename = f"sotuvlar_{start_date_obj.strftime('%d.%m.%Y')}.xlsx"
            else:
                filename = f"sotuvlar_{start_date_obj.strftime('%d.%m.%Y')}_dan_{end_date_obj.strftime('%d.%m.%Y')}_gacha.xlsx"
        else:
            filename = f"sotuvlar_{timezone.now().strftime('%d.%m.%Y')}.xlsx"
            
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        # Save workbook to response
        wb.save(response)
        
        logger.info(f"Exported {queryset.count()} sales to Excel")
        return response

    except Exception as e:
        logger.error(f"Error exporting sales to Excel: {e}")
        return HttpResponse("Excel export xatolik bilan yakunlandi.", status=500)
