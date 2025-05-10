from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Sum, F, Case, When, Value, DecimalField, ExpressionWrapper, Count
from datetime import timedelta
from decimal import Decimal
from .models import Agent, Seller, TicketSale, Payment, PaymentMethod
from apps.stock.models import TicketPurchase
import django_filters
from django.urls import reverse, reverse_lazy
from django.db import transaction
from apps.stock.utils import AdminRequiredMixin, is_admin
import xlwt  # Import for Excel export
from django.utils.translation import gettext as _


class TicketSaleFilter(django_filters.FilterSet):
    """FilterSet for ticket sales"""
    search = django_filters.CharFilter(method='filter_search', label="Qidirish")
    date_filter = django_filters.ChoiceFilter(
        choices=(
            ('today', 'Bugun'),
            ('week', 'Shu hafta'),
            ('month', 'Shu oy'),
            ('custom', 'Maxsus oraliq'),
        ),
        method='filter_date',
        empty_label='Barcha Sanalar',
        label='Sana Oralig\'i',
    )
    start_date = django_filters.DateFilter(field_name='sale_date', lookup_expr='gte', label="Boshlanish sanasi")
    end_date = django_filters.DateFilter(field_name='sale_date', lookup_expr='lte', label="Tugash sanasi")
    customer_type = django_filters.ChoiceFilter(
        choices=TicketSale.CUSTOMER_TYPES,
        empty_label='Barcha Mijoz Turlari',
        label="Mijoz Turi"
    )
    agent = django_filters.ModelChoiceFilter(
        queryset=Agent.objects.all(),
        empty_label='Barcha Agentlar',
        label="Agent"
    )
    seller = django_filters.ModelChoiceFilter(
        queryset=Seller.objects.all(),
        empty_label='Barcha Sotuvchilar',
        label="Sotuvchi"
    )
    payment_method = django_filters.ModelChoiceFilter(
        queryset=PaymentMethod.objects.filter(is_active=True),
        method='filter_payment_method',
        empty_label='Barcha To\'lov Usullari',
        label="To'lov Usuli"
    )
    currency = django_filters.ChoiceFilter(
        choices=TicketSale.CURRENCY_CHOICES,
        empty_label='Barcha Valyutalar',
        label="Valyuta"
    )
    sort_by = django_filters.ChoiceFilter(
        choices=(
            ('-sale_date', 'Eng Yangi'),
            ('sale_date', 'Eng Eski'),
            ('-profit', 'Foyda (Yuqoridan Pastga)'),
        ),
        method='filter_sort_by',
        empty_label=None,
        label='Saralash',
        initial='-sale_date',
    )
    
    def filter_search(self, queryset, name, value):
        if value:
            return queryset.filter(
                Q(sale_id__icontains=value) |
                Q(customer_name__icontains=value) |
                Q(agent__name__icontains=value) |
                Q(notes__icontains=value)
            )
        return queryset
    
    def filter_date(self, queryset, name, value):
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        if value == 'today':
            return queryset.filter(sale_date__gte=today)
        elif value == 'week':
            start_of_week = today - timedelta(days=today.weekday())
            return queryset.filter(sale_date__gte=start_of_week)
        elif value == 'month':
            start_of_month = today.replace(day=1)
            return queryset.filter(sale_date__gte=start_of_month)
        return queryset
    
    def filter_payment_method(self, queryset, name, value):
        """Filter sales by payment method"""
        if value:
            return queryset.filter(payments__payment_method=value)
        return queryset
    
    def filter_sort_by(self, queryset, name, value):
        return queryset.order_by(value)
    
    class Meta:
        model = TicketSale
        fields = [
            'search', 'date_filter', 'start_date', 'end_date',
            'customer_type', 'agent', 'seller', 'payment_method', 'currency'
        ]


class TicketSaleListView(AdminRequiredMixin, LoginRequiredMixin, ListView):
    """View for listing ticket sales with filtering and sorting"""

    model = TicketSale
    template_name = "finance/ticket_sale_list.html"
    context_object_name = "sales"
    paginate_by = 10
    filterset_class = TicketSaleFilter

    def get_queryset(self):
        queryset = TicketSale.objects.all().select_related(
            "agent", "seller", "ticket_purchase"
        ).prefetch_related(
            "payments__payment_method"
        )
        
        # Apply filtering
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter form
        context["filterset"] = self.filterset
        
        # Get filtered queryset for aggregations
        sales = self.filterset.qs
        
        # Expression for total price (unit_price * quantity) with explicit Decimal output
        total_price_expr = ExpressionWrapper(
            F("unit_price") * F("quantity"), output_field=DecimalField(max_digits=20, decimal_places=2)
        )

        # Do one single aggregation query with conditional expressions
        totals = sales.aggregate(
            total_quantity=Sum("quantity"),
            usd_total_sum=Sum(
                Case(
                    When(currency="USD", then=total_price_expr),
                    default=Value(0),
                    output_field=DecimalField(max_digits=20, decimal_places=2),
                )
            ),
            uzs_total_sum=Sum(
                Case(
                    When(currency="UZS", then=total_price_expr),
                    default=Value(0),
                    output_field=DecimalField(max_digits=20, decimal_places=2),
                )
            ),
            usd_profit=Sum(
                Case(
                    When(currency="USD", profit__isnull=False, then=F("profit")),
                    default=Value(0),
                    output_field=DecimalField(max_digits=20, decimal_places=2),
                )
            ),
            uzs_profit=Sum(
                Case(
                    When(currency="UZS", profit__isnull=False, then=F("profit")),
                    default=Value(0),
                    output_field=DecimalField(max_digits=20, decimal_places=2),
                )
            ),
        )
        
        # Add totals to context
        context.update(totals)
        
        # Add agents and sellers for filter dropdowns and add to context as JSON-ready values
        agents = Agent.objects.all()
        sellers = Seller.objects.all()
        ticket_purchases = TicketPurchase.objects.all()
        payment_methods = PaymentMethod.objects.filter(is_active=True)
        
        context["agents"] = agents
        context["sellers"] = sellers
        context["ticket_purchases"] = ticket_purchases
        context["payment_methods"] = payment_methods
        
        # Prepare JSON data for JavaScript
        context["js_data"] = {
            "agents": [{"id": str(agent.id), "name": agent.name} for agent in agents],
            "sellers": [{"id": str(seller.id), "name": seller.name} for seller in sellers],
            "ticket_purchases": [
                {
                    "id": str(purchase.id),
                    "purchase_id": purchase.purchase_id,
                    "supplier_name": purchase.supplier.name,
                    "unit_price": float(purchase.unit_price),
                    "currency": purchase.currency
                }
                for purchase in ticket_purchases
            ],
            "payment_methods": [
                {
                    "id": str(method.id),
                    "name": method.name,
                    "method_type": method.method_type,
                    "currency": method.currency,
                    "display_name": str(method)
                }
                for method in payment_methods
            ],
            "sale_create_url": reverse('finance:sale_create'),
            "excel_export_url": reverse('finance:export_sales') + "?" + self.request.GET.urlencode()
        }
        
        # Keep track of applied filters for clearing
        active_filters = {}
        for key, value in self.request.GET.items():
            if key != "page" and value:  # Exclude pagination parameter
                active_filters[key] = value
        context["active_filters"] = active_filters

        return context


@login_required
@user_passes_test(is_admin, login_url=reverse_lazy('login'))
@require_POST
def sale_create(request):
    """Handle the AJAX form submission for creating a new ticket sale"""
    # Check for AJAX request
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        try:
            # Extract form data
            customer_type = request.POST.get("customer_type")
            customer_name = request.POST.get("customer_name", "")
            agent_id = request.POST.get("agent")
            seller_id = request.POST.get("seller")
            ticket_purchase_id = request.POST.get("ticket_purchase")
            quantity = int(request.POST.get("quantity")) # Convert to int early
            unit_price = Decimal(request.POST.get("unit_price")) # Convert to Decimal early
            currency = request.POST.get("currency")
            notes = request.POST.get("notes", "")
            sale_date_str = request.POST.get("sale_date")
            
            # Payment method details (for individual customers)
            payment_method_id = request.POST.get("payment_method")

            # --- Validation --- 
            if not all([customer_type, seller_id, ticket_purchase_id, quantity, unit_price, currency]):
                return JsonResponse({"success": False, "errors": "Missing required fields."}, status=400)
            
            if quantity <= 0:
                 return JsonResponse({"success": False, "errors": "Quantity must be positive."}, status=400)

            # Get the related TicketPurchase object
            try:
                ticket_purchase = TicketPurchase.objects.get(id=ticket_purchase_id)
            except TicketPurchase.DoesNotExist:
                 return JsonResponse({"success": False, "errors": "Invalid Ticket Purchase ID."}, status=400)

            # Check if enough quantity remaining
            if quantity > ticket_purchase.quantity_remaining:
                 return JsonResponse({
                    "success": False, 
                    "errors": f"Not enough stock for purchase {ticket_purchase.purchase_id}. Available: {ticket_purchase.quantity_remaining}"
                 }, status=400)
                 
            # For individual customers, payment method is required
            if customer_type == "individual" and not payment_method_id:
                return JsonResponse({"success": False, "errors": "Payment method is required for individual customers."}, status=400)
            # --- End Validation ---

            # Convert date string to a datetime object if provided
            from django.utils.dateparse import parse_datetime
            sale_date = (
                parse_datetime(sale_date_str) if sale_date_str else timezone.now()
            )

            # Create the sale object
            sale_data = {
                "sale_date": sale_date,
                "customer_type": customer_type,
                "seller_id": seller_id,
                "ticket_purchase": ticket_purchase, # Use the object directly
                "quantity": quantity, 
                "unit_price": unit_price,
                "currency": currency,
                "notes": notes,
            }

            # Set customer name or agent based on customer type
            if customer_type == "agent":
                sale_data["agent_id"] = agent_id
                sale_data["customer_name"] = None
            else:
                sale_data["agent"] = None
                sale_data["customer_name"] = customer_name

            # Use transaction to ensure atomicity
            with transaction.atomic():
                # Create the sale
                sale = TicketSale.objects.create(**sale_data)
                
                # Update the quantity_sold on the TicketPurchase
                ticket_purchase.quantity_sold = F("quantity_sold") + quantity
                ticket_purchase.save(update_fields=["quantity_sold"])
                
                # If customer type is individual, automatically create payment record
                if customer_type == "individual":
                    # Get the payment method
                    payment_method = None
                    if payment_method_id:
                        try:
                            payment_method = PaymentMethod.objects.get(id=payment_method_id)
                            
                            # Validate currency matching
                            if payment_method.currency != currency:
                                return JsonResponse({
                                    "success": False, 
                                    "errors": f"Payment method currency ({payment_method.currency}) must match sale currency ({currency})."
                                }, status=400)
                        except PaymentMethod.DoesNotExist:
                            return JsonResponse({"success": False, "errors": "Invalid Payment Method ID."}, status=400)
                    
                    Payment.objects.create(
                        payment_date=sale_date,
                        ticket_sale=sale,
                        amount=sale.total_price,  # Use the total_price property
                        currency=currency,
                        payment_method=payment_method,
                        payment_type="full",
                        notes=f"Automatic payment for sale {sale.sale_id}"
                    )
            
            # Get ticket purchase details for the response
            payment_method_info = None
            if customer_type == "individual" and payment_method:
                payment_method_info = {
                    "id": str(payment_method.id),
                    "name": payment_method.name,
                    "method_type": payment_method.method_type,
                    "display_name": str(payment_method)
                }
            
            return JsonResponse({
                "success": True,
                "sale": {
                    "sale_id": sale.sale_id,
                    "sale_date": sale.sale_date.strftime("%b %d, %Y"),
                    "customer": sale.agent.name if sale.agent else sale.customer_name,
                    "seller": sale.seller.name,
                    "ticket_purchase": f"{ticket_purchase.purchase_id} - {ticket_purchase.supplier.name}",
                    "quantity": sale.quantity,
                    "unit_price": float(sale.unit_price),  # Convert Decimal to float for JSON
                    "total_price": float(sale.total_price),
                    "profit": float(sale.profit) if sale.profit is not None else None,
                    "currency": sale.currency,
                    "payment_created": customer_type == "individual",  # Indicate if payment was created
                    "payment_method": payment_method_info
                }
            })

        except Exception as e:
            import traceback

            return JsonResponse(
                {
                    "success": False,
                    "errors": str(e),
                    "traceback": traceback.format_exc(),
                },
                status=400,
            )

    return JsonResponse({"success": False, "errors": "Invalid request"}, status=400)


class PaymentFilter(django_filters.FilterSet):
    """FilterSet for payments"""
    search = django_filters.CharFilter(method='filter_search', label="Qidirish")
    date_filter = django_filters.ChoiceFilter(
        choices=(
            ('today', 'Bugun'),
            ('week', 'Shu hafta'),
            ('month', 'Shu oy'),
            ('custom', 'Maxsus oraliq'),
        ),
        method='filter_date',
        empty_label='Barcha Sanalar',
        label='Sana Oralig\'i',
    )
    start_date = django_filters.DateFilter(field_name='payment_date', lookup_expr='gte', label="Boshlanish sanasi")
    end_date = django_filters.DateFilter(field_name='payment_date', lookup_expr='lte', label="Tugash sanasi")
    payment_type = django_filters.ChoiceFilter(
        choices=Payment.PAYMENT_TYPES,
        empty_label='Barcha To\'lov Turlari',
        label="To'lov Turi"
    )
    payment_method = django_filters.ModelChoiceFilter(
        queryset=PaymentMethod.objects.filter(is_active=True),
        empty_label='Barcha To\'lov Usullari',
        label="To'lov Usuli"
    )
    currency = django_filters.ChoiceFilter(
        choices=TicketSale.CURRENCY_CHOICES,
        empty_label='Barcha Valyutalar',
        label="Valyuta"
    )
    sort_by = django_filters.ChoiceFilter(
        choices=(
            ('-payment_date', 'Eng Yangi'),
            ('payment_date', 'Eng Eski'),
            ('-amount', 'Miqdor (Yuqoridan Pastga)'),
        ),
        method='filter_sort_by',
        empty_label=None,
        label='Saralash',
        initial='-payment_date',
    )
    
    def filter_search(self, queryset, name, value):
        if value:
            return queryset.filter(
                Q(payment_id__icontains=value) |
                Q(ticket_sale__sale_id__icontains=value) |
                Q(ticket_sale__customer_name__icontains=value) |
                Q(ticket_sale__agent__name__icontains=value) |
                Q(notes__icontains=value)
            )
        return queryset
    
    def filter_date(self, queryset, name, value):
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        if value == 'today':
            return queryset.filter(payment_date__gte=today)
        elif value == 'week':
            start_of_week = today - timedelta(days=today.weekday())
            return queryset.filter(payment_date__gte=start_of_week)
        elif value == 'month':
            start_of_month = today.replace(day=1)
            return queryset.filter(payment_date__gte=start_of_month)
        return queryset
    
    def filter_sort_by(self, queryset, name, value):
        return queryset.order_by(value)
    
    class Meta:
        model = Payment
        fields = [
            'search', 'date_filter', 'start_date', 'end_date',
            'payment_type', 'payment_method', 'currency'
        ]


class PaymentListView(AdminRequiredMixin, LoginRequiredMixin, ListView):
    """View for listing payments with filtering and sorting"""
    model = Payment
    template_name = "finance/payment_list.html"
    context_object_name = "payments"
    paginate_by = 10
    filterset_class = PaymentFilter

    def get_queryset(self):
        queryset = Payment.objects.all().select_related(
            "ticket_sale", "ticket_sale__agent", "ticket_sale__seller"
        )
        
        # Apply filtering
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter form
        context["filterset"] = self.filterset
        
        # Get filtered queryset for aggregations
        payments = self.filterset.qs
        
        # Do one single aggregation query with conditional expressions
        totals = payments.aggregate(
            usd_total=Sum(
                Case(
                    When(currency="USD", then=F("amount")),
                    default=Value(0),
                    output_field=DecimalField(max_digits=20, decimal_places=2),
                )
            ),
            uzs_total=Sum(
                Case(
                    When(currency="UZS", then=F("amount")),
                    default=Value(0),
                    output_field=DecimalField(max_digits=20, decimal_places=2),
                )
            ),
        )
        
        # Add totals to context
        context.update(totals)
        
        # Keep track of applied filters for clearing
        active_filters = {}
        for key, value in self.request.GET.items():
            if key != "page" and value:  # Exclude pagination parameter
                active_filters[key] = value
        context["active_filters"] = active_filters

        return context


@login_required
@user_passes_test(is_admin, login_url=reverse_lazy('login'))
def export_sales_to_excel(request):
    """Export ticket sales to Excel"""
    # Reuse the same filter logic from list view
    queryset = TicketSale.objects.all().select_related("agent", "seller", "ticket_purchase")
    filterset = TicketSaleFilter(request.GET, queryset=queryset)
    sales = filterset.qs
    
    # Create workbook and add a worksheet
    workbook = xlwt.Workbook(encoding='utf-8')
    worksheet = workbook.add_sheet(_('Ticket Sales'))
    
    # Define styles
    header_style = xlwt.easyxf('font: bold on; align: wrap on, vert centre, horiz center; pattern: pattern solid, fore_color gray25;')
    date_style = xlwt.easyxf('align: horiz left; ', num_format_str='YYYY-MM-DD')
    number_style = xlwt.easyxf('align: horiz right;')
    currency_style_usd = xlwt.easyxf('align: horiz right;', num_format_str='$#,##0.00')
    currency_style_uzs = xlwt.easyxf('align: horiz right;', num_format_str='#,##0.00 [$UZS];[RED]-#,##0.00 [$UZS]')
    profit_style_usd = xlwt.easyxf('align: horiz right;', num_format_str='$#,##0.00;[RED]-$#,##0.00')
    profit_style_uzs = xlwt.easyxf('align: horiz right;', num_format_str='#,##0.00 [$UZS];[RED]-#,##0.00 [$UZS]')
    
    # Set column headers
    headers = [
        _('Sale ID'), 
        _('Date'), 
        _('Customer'), 
        _('Seller'), 
        _('Purchase ID'),
        _('Quantity'), 
        _('Unit Price'), 
        _('Total'), 
        _('Profit'),
        _('Currency'),
        _('Payment Method')
    ]
    
    # Set column widths
    col_widths = [15, 15, 20, 15, 15, 10, 15, 15, 15, 10, 25]
    for i, width in enumerate(col_widths):
        worksheet.col(i).width = 256 * width  # 256 = 1 character width
    
    # Write headers
    for col, header in enumerate(headers):
        worksheet.write(0, col, header, header_style)
    
    # Write data rows
    row = 1
    for sale in sales:
        worksheet.write(row, 0, sale.sale_id)
        worksheet.write(row, 1, sale.sale_date, date_style)
        
        # Format customer name with agent indicator
        if sale.customer_type == 'agent' and sale.agent:
            customer = f"{sale.agent.name} (Agent)"
        else:
            customer = sale.customer_name
        worksheet.write(row, 2, customer)
        
        worksheet.write(row, 3, sale.seller.name)
        worksheet.write(row, 4, sale.ticket_purchase.purchase_id)
        worksheet.write(row, 5, sale.quantity, number_style)
        
        # Format currency values based on currency type
        if sale.currency == 'USD':
            worksheet.write(row, 6, float(sale.unit_price), currency_style_usd)
            worksheet.write(row, 7, float(sale.total_price), currency_style_usd)
            if sale.profit is not None:
                worksheet.write(row, 8, float(sale.profit), profit_style_usd)
            else:
                worksheet.write(row, 8, '—')
        else:  # UZS
            worksheet.write(row, 6, float(sale.unit_price), currency_style_uzs)
            worksheet.write(row, 7, float(sale.total_price), currency_style_uzs)
            if sale.profit is not None:
                worksheet.write(row, 8, float(sale.profit), profit_style_uzs)
            else:
                worksheet.write(row, 8, '—')
                
        worksheet.write(row, 9, sale.currency)
        
        # Get payment method for individual customers
        payment_method = "—"
        if sale.customer_type == 'individual':
            # Get the first payment for this sale (individual customers usually have one full payment)
            payment = Payment.objects.filter(ticket_sale=sale).first()
            if payment and payment.payment_method:
                payment_method = str(payment.payment_method)
        
        worksheet.write(row, 10, payment_method)
        
        row += 1
    
    # Prepare response
    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = 'attachment; filename="ticket_sales.xls"'
    workbook.save(response)
    
    return response


class PaymentMethodListView(AdminRequiredMixin, LoginRequiredMixin, ListView):
    """View for listing payment methods"""
    model = PaymentMethod
    template_name = "finance/payment_method_list.html"
    context_object_name = "payment_methods"
    paginate_by = 20

    def get_queryset(self):
        queryset = PaymentMethod.objects.all()
        
        # Apply filtering by search term
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(account_number__icontains=search) |
                Q(details__icontains=search)
            )
            
        # Apply filtering by method type
        method_type = self.request.GET.get('method_type')
        if method_type:
            queryset = queryset.filter(method_type=method_type)
            
        # Apply filtering by currency
        currency = self.request.GET.get('currency')
        if currency:
            queryset = queryset.filter(currency=currency)
            
        # Apply filtering by status
        status = self.request.GET.get('status')
        if status == 'active':
            queryset = queryset.filter(is_active=True)
        elif status == 'inactive':
            queryset = queryset.filter(is_active=False)
            
        # Apply sorting
        sort = self.request.GET.get('sort', 'name')
        queryset = queryset.order_by(sort)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['method_types'] = dict(PaymentMethod.METHOD_TYPES)
        context['currencies'] = dict(PaymentMethod.CURRENCY_CHOICES)
        
        # Maintain search parameters for pagination
        search_params = {k: v for k, v in self.request.GET.items() if k != 'page'}
        context['search_params'] = search_params
        
        # Create empty method for modal form
        context['new_method'] = PaymentMethod()
        
        return context


@login_required
@user_passes_test(is_admin, login_url=reverse_lazy('login'))
@require_POST
def payment_method_create(request):
    """Handle the form submission for creating a new payment method"""
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        try:
            # Extract form data
            name = request.POST.get("name")
            method_type = request.POST.get("method_type")
            currency = request.POST.get("currency")
            account_number = request.POST.get("account_number", "")
            details = request.POST.get("details", "")
            is_active = request.POST.get("is_active") == "on"
            
            # Validation
            if not all([name, method_type, currency]):
                return JsonResponse({"success": False, "errors": "Missing required fields."}, status=400)
            
            # Check currency matches method type convention
            if method_type == "plastic_card" and currency != "UZS":
                return JsonResponse(
                    {"success": False, "errors": "Plastic cards must use UZS currency."},
                    status=400,
                )
            elif method_type == "visa_card" and currency != "USD":
                return JsonResponse(
                    {"success": False, "errors": "VISA cards must use USD currency."},
                    status=400,
                )
            elif method_type == "cash_uzs" and currency != "UZS":
                return JsonResponse(
                    {"success": False, "errors": "Cash UZS must use UZS currency."},
                    status=400,
                )
            elif method_type == "cash_usd" and currency != "USD":
                return JsonResponse(
                    {"success": False, "errors": "Cash USD must use USD currency."},
                    status=400,
                )
            
            # Create payment method
            payment_method = PaymentMethod.objects.create(
                name=name,
                method_type=method_type,
                currency=currency,
                account_number=account_number,
                details=details,
                is_active=is_active
            )
            
            return JsonResponse({
                "success": True,
                "message": "Payment method created successfully.",
                "payment_method": {
                    "id": payment_method.id,
                    "name": payment_method.name,
                    "method_type": payment_method.method_type,
                    "method_type_display": payment_method.get_method_type_display(),
                    "currency": payment_method.currency,
                    "account_number": payment_method.account_number,
                    "is_active": payment_method.is_active
                }
            })
            
        except Exception as e:
            return JsonResponse({"success": False, "errors": str(e)}, status=400)
            
    return JsonResponse({"success": False, "errors": "Invalid request."}, status=400)


@login_required
@user_passes_test(is_admin, login_url=reverse_lazy('login'))
@require_POST
def payment_method_update(request, pk):
    """Handle the form submission for updating a payment method"""
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        try:
            # Get payment method
            payment_method = get_object_or_404(PaymentMethod, pk=pk)
            
            # Extract form data
            payment_method.name = request.POST.get("name")
            payment_method.method_type = request.POST.get("method_type")
            payment_method.currency = request.POST.get("currency")
            payment_method.account_number = request.POST.get("account_number", "")
            payment_method.details = request.POST.get("details", "")
            payment_method.is_active = request.POST.get("is_active") == "on"
            
            # Validation
            if not all([payment_method.name, payment_method.method_type, payment_method.currency]):
                return JsonResponse({"success": False, "errors": "Missing required fields."}, status=400)
            
            # Check currency matches method type convention
            if payment_method.method_type == "plastic_card" and payment_method.currency != "UZS":
                return JsonResponse(
                    {"success": False, "errors": "Plastic cards must use UZS currency."},
                    status=400,
                )
            elif payment_method.method_type == "visa_card" and payment_method.currency != "USD":
                return JsonResponse(
                    {"success": False, "errors": "VISA cards must use USD currency."},
                    status=400,
                )
            elif payment_method.method_type == "cash_uzs" and payment_method.currency != "UZS":
                return JsonResponse(
                    {"success": False, "errors": "Cash UZS must use UZS currency."},
                    status=400,
                )
            elif payment_method.method_type == "cash_usd" and payment_method.currency != "USD":
                return JsonResponse(
                    {"success": False, "errors": "Cash USD must use USD currency."},
                    status=400,
                )
            
            # Save payment method
            payment_method.save()
            
            return JsonResponse({
                "success": True,
                "message": "Payment method updated successfully.",
                "payment_method": {
                    "id": payment_method.id,
                    "name": payment_method.name,
                    "method_type": payment_method.method_type,
                    "method_type_display": payment_method.get_method_type_display(),
                    "currency": payment_method.currency,
                    "account_number": payment_method.account_number,
                    "is_active": payment_method.is_active
                }
            })
            
        except Exception as e:
            return JsonResponse({"success": False, "errors": str(e)}, status=400)
            
    return JsonResponse({"success": False, "errors": "Invalid request."}, status=400)


@login_required
@user_passes_test(is_admin, login_url=reverse_lazy('login'))
@require_POST
def payment_method_toggle_status(request, pk):
    """Toggle the active status of a payment method"""
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        try:
            # Get payment method
            payment_method = get_object_or_404(PaymentMethod, pk=pk)
            
            # Toggle status
            payment_method.is_active = not payment_method.is_active
            payment_method.save(update_fields=["is_active"])
            
            # Check if this payment method is being used in any payments
            active_payments = Payment.objects.filter(payment_method=payment_method).exists()
            
            return JsonResponse({
                "success": True,
                "is_active": payment_method.is_active,
                "active_payments": active_payments,
                "message": f"Payment method {'activated' if payment_method.is_active else 'deactivated'} successfully."
            })
            
        except Exception as e:
            return JsonResponse({"success": False, "errors": str(e)}, status=400)
            
    return JsonResponse({"success": False, "errors": "Invalid request."}, status=400)


class FinancialReportFilter(django_filters.FilterSet):
    date_filter = django_filters.ChoiceFilter(
        choices=(
            ('today', 'Bugun'),
            ('week', 'Shu hafta'),
            ('month', 'Shu oy'),
            ('custom', 'Maxsus oraliq'),
        ),
        method='filter_date_range',
        empty_label='Barcha Sanalar',
        label='Sana Oralig\'i',
    )
    start_date = django_filters.DateFilter(field_name='payment_date', lookup_expr='gte', label="Boshlanish sanasi")
    end_date = django_filters.DateFilter(field_name='payment_date', lookup_expr='lte', label="Tugash sanasi")
    payment_method = django_filters.ModelChoiceFilter(
        queryset=PaymentMethod.objects.filter(is_active=True),
        field_name='payment_method',
        empty_label='Barcha To\'lov Usullari',
        label="To\'lov Usuli"
    )
    currency = django_filters.ChoiceFilter(
        field_name='currency',
        choices=TicketSale.CURRENCY_CHOICES,
        empty_label='Barcha Valyutalar',
        label="Valyuta"
    )

    def filter_date_range(self, queryset, name, value):
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if value == 'today':
            return queryset.filter(payment_date__gte=today)
        elif value == 'week':
            start_of_week = today - timedelta(days=today.weekday())
            return queryset.filter(payment_date__gte=start_of_week)
        elif value == 'month':
            start_of_month = today.replace(day=1)
            return queryset.filter(payment_date__gte=start_of_month)
        return queryset

    class Meta:
        model = Payment
        fields = ['date_filter', 'start_date', 'end_date', 'payment_method', 'currency']


class FinancialReportView(AdminRequiredMixin, LoginRequiredMixin, ListView):
    model = Payment
    template_name = "finance/financial_report.html" 
    context_object_name = "payments_list"
    paginate_by = 20
    filterset_class = FinancialReportFilter

    def get_queryset(self):
        queryset = Payment.objects.select_related(
            "ticket_sale", 
            "ticket_sale__agent", 
            "ticket_sale__seller", 
            "payment_method"
        ).order_by('-payment_date')
        
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        summary_queryset = self.filterset.qs 
        
        payment_summary_by_method = summary_queryset.values(
            'payment_method__name', 
            'payment_method__id', 
            'currency'
        ).annotate(
            total_amount=Sum('amount'),
            payment_count=Count('id') 
        ).order_by('payment_method__name', 'currency')
        
        context["payment_summary"] = payment_summary_by_method
        context["filterset"] = self.filterset
        context["payment_methods_all"] = PaymentMethod.objects.all()
        
        active_filters = {}
        for key, value in self.request.GET.items():
            if key != "page" and value:
                active_filters[key] = value
        context["active_filters"] = active_filters
        
        return context
