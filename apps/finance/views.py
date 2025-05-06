from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Q, Sum, F, Case, When, Value, DecimalField, ExpressionWrapper
from datetime import timedelta
from decimal import Decimal
from .models import Agent, Seller, TicketSale
from apps.stock.models import TicketPurchase
import django_filters
from django.urls import reverse


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
    
    def filter_sort_by(self, queryset, name, value):
        return queryset.order_by(value)
    
    class Meta:
        model = TicketSale
        fields = [
            'search', 'date_filter', 'start_date', 'end_date',
            'customer_type', 'agent', 'seller', 'currency'
        ]


class TicketSaleListView(LoginRequiredMixin, ListView):
    """View for listing ticket sales with filtering and sorting"""

    model = TicketSale
    template_name = "finance/ticket_sale_list.html"
    context_object_name = "sales"
    paginate_by = 10
    filterset_class = TicketSaleFilter

    def get_queryset(self):
        queryset = TicketSale.objects.all().select_related(
            "agent", "seller", "ticket_purchase"
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
        
        context["agents"] = agents
        context["sellers"] = sellers
        context["ticket_purchases"] = ticket_purchases
        
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
            "sale_create_url": reverse('finance:sale_create')
        }
        
        # Keep track of applied filters for clearing
        active_filters = {}
        for key, value in self.request.GET.items():
            if key != "page" and value:  # Exclude pagination parameter
                active_filters[key] = value
        context["active_filters"] = active_filters

        return context


@login_required
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

            # --- Transactional Update (Recommended) --- 
            # Consider wrapping this in a transaction if atomicity is critical
            # from django.db import transaction
            # with transaction.atomic():
            # Create the sale
            sale = TicketSale.objects.create(**sale_data)
            
            # Update the quantity_sold on the TicketPurchase
            ticket_purchase.quantity_sold = F("quantity_sold") + quantity
            ticket_purchase.save(update_fields=["quantity_sold"])
            # --- End Transactional Update ---
            
            # Refresh ticket_purchase from DB to get updated quantity_sold if needed
            # ticket_purchase.refresh_from_db()

            # Get ticket purchase details for the response
            # ticket_purchase is already fetched and updated
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
