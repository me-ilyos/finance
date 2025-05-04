from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Q, Sum, F
from datetime import timedelta
from decimal import Decimal
from .models import Agent, Seller, TicketSale
from apps.stock.models import TicketPurchase


class TicketSaleListView(LoginRequiredMixin, ListView):
    """View for listing ticket sales with filtering and sorting"""

    model = TicketSale
    template_name = "finance/ticket_sale_list.html"
    context_object_name = "sales"
    paginate_by = 10

    def get_queryset(self):
        queryset = TicketSale.objects.all().select_related(
            "agent", "seller", "ticket_purchase"
        )

        # Search functionality
        search_query = self.request.GET.get("search", "")
        if search_query:
            queryset = queryset.filter(
                Q(sale_id__icontains=search_query)
                | Q(customer_name__icontains=search_query)
                | Q(agent__name__icontains=search_query)
                | Q(notes__icontains=search_query)
            )

        # Date filtering
        date_filter = self.request.GET.get("date_filter", "today")
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

        if date_filter == "today":
            queryset = queryset.filter(sale_date__gte=today)
        elif date_filter == "week":
            start_of_week = today - timedelta(days=today.weekday())
            queryset = queryset.filter(sale_date__gte=start_of_week)
        elif date_filter == "month":
            start_of_month = today.replace(day=1)
            queryset = queryset.filter(sale_date__gte=start_of_month)
        elif date_filter == "custom":
            start_date = self.request.GET.get("start_date")
            end_date = self.request.GET.get("end_date")
            if start_date and end_date:
                queryset = queryset.filter(
                    sale_date__gte=start_date,
                    sale_date__lte=end_date + " 23:59:59",
                )

        # Customer type filtering
        customer_type = self.request.GET.get("customer_type")
        if customer_type:
            queryset = queryset.filter(customer_type=customer_type)

        # Agent filtering
        agent_id = self.request.GET.get("agent")
        if agent_id:
            queryset = queryset.filter(agent_id=agent_id)

        # Seller filtering
        seller_id = self.request.GET.get("seller")
        if seller_id:
            queryset = queryset.filter(seller_id=seller_id)

        # Currency filtering
        currency = self.request.GET.get("currency")
        if currency:
            queryset = queryset.filter(currency=currency)

        # Sorting
        sort_by = self.request.GET.get("sort_by", "-sale_date")
        queryset = queryset.order_by(sort_by)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add filters to context
        context["search_query"] = self.request.GET.get("search", "")
        context["date_filter"] = self.request.GET.get("date_filter", "today")
        context["customer_type"] = self.request.GET.get("customer_type", "")
        context["agent_id"] = self.request.GET.get("agent", "")
        context["seller_id"] = self.request.GET.get("seller", "")
        context["currency"] = self.request.GET.get("currency", "")
        context["sort_by"] = self.request.GET.get("sort_by", "-sale_date")

        # Add agents and sellers for filter dropdowns
        context["agents"] = Agent.objects.all()
        context["sellers"] = Seller.objects.all()
        context["ticket_purchases"] = TicketPurchase.objects.all()

        # Calculate totals for current filter
        sales = self.get_queryset()

        # Total tickets sold (sum of quantities, not count of sales)
        context["total_quantity"] = sales.aggregate(total=Sum("quantity"))["total"] or 0

        # Total USD profit
        usd_profit = (
            sales.filter(currency="USD", profit__isnull=False).aggregate(
                total=Sum("profit")
            )["total"]
            or 0
        )
        context["usd_profit"] = usd_profit

        # Total UZS profit
        uzs_profit = (
            sales.filter(currency="UZS", profit__isnull=False).aggregate(
                total=Sum("profit")
            )["total"]
            or 0
        )
        context["uzs_profit"] = uzs_profit

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
            quantity = request.POST.get("quantity")
            unit_price = request.POST.get("unit_price")
            currency = request.POST.get("currency")
            notes = request.POST.get("notes", "")

            # Convert date string to a datetime object if provided
            from django.utils.dateparse import parse_datetime

            sale_date_str = request.POST.get("sale_date")
            sale_date = (
                parse_datetime(sale_date_str) if sale_date_str else timezone.now()
            )

            # Create the sale object
            sale_data = {
                "sale_date": sale_date,
                "customer_type": customer_type,
                "seller_id": seller_id,
                "ticket_purchase_id": ticket_purchase_id,
                "quantity": int(quantity),
                "unit_price": Decimal(unit_price),  # Use Decimal instead of float
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

            # Create the sale
            sale = TicketSale.objects.create(**sale_data)

            # Get ticket purchase details for the response
            ticket_purchase = sale.ticket_purchase
            purchase_info = (
                f"{ticket_purchase.purchase_id} - {ticket_purchase.supplier.name}"
            )

            # Format profit for display with space as thousand separator
            formatted_profit = "—"
            if sale.profit is not None:
                # Convert to string and format with spaces
                profit_str = f"{float(sale.profit):.2f}"
                # Split at decimal point
                profit_parts = profit_str.split(".")
                # Format the integer part with space as thousand separator
                if len(profit_parts[0]) > 3:
                    formatted_int = ""
                    for i, char in enumerate(reversed(profit_parts[0])):
                        if i > 0 and i % 3 == 0:
                            formatted_int = " " + formatted_int
                        formatted_int = char + formatted_int
                    profit_parts[0] = formatted_int

                # Combine with currency
                if sale.currency == "USD":
                    formatted_profit = f"${profit_parts[0]}.{profit_parts[1]}"
                else:
                    formatted_profit = f"{profit_parts[0]}.{profit_parts[1]} UZS"

            # Format unit price and total price
            unit_price_float = float(sale.unit_price)
            total_price_float = float(sale.total_price)

            # Convert to string and format with spaces
            unit_price_str = f"{unit_price_float:.2f}"
            total_price_str = f"{total_price_float:.2f}"

            # Split at decimal point
            unit_price_parts = unit_price_str.split(".")
            total_price_parts = total_price_str.split(".")

            # Format the integer part with space as thousand separator
            if len(unit_price_parts[0]) > 3:
                formatted_unit_int = ""
                for i, char in enumerate(reversed(unit_price_parts[0])):
                    if i > 0 and i % 3 == 0:
                        formatted_unit_int = " " + formatted_unit_int
                    formatted_unit_int = char + formatted_unit_int
                unit_price_parts[0] = formatted_unit_int

            if len(total_price_parts[0]) > 3:
                formatted_total_int = ""
                for i, char in enumerate(reversed(total_price_parts[0])):
                    if i > 0 and i % 3 == 0:
                        formatted_total_int = " " + formatted_total_int
                    formatted_total_int = char + formatted_total_int
                total_price_parts[0] = formatted_total_int

            # Combine with currency
            if sale.currency == "USD":
                formatted_unit_price = f"${unit_price_parts[0]}.{unit_price_parts[1]}"
                formatted_total_price = (
                    f"${total_price_parts[0]}.{total_price_parts[1]}"
                )
            else:
                formatted_unit_price = (
                    f"{unit_price_parts[0]}.{unit_price_parts[1]} UZS"
                )
                formatted_total_price = (
                    f"{total_price_parts[0]}.{total_price_parts[1]} UZS"
                )

            # Return success response with formatted data
            return JsonResponse(
                {
                    "success": True,
                    "sale": {
                        "sale_id": sale.sale_id,
                        "sale_date": sale.sale_date.strftime("%b %d, %Y"),
                        "customer": (
                            sale.agent.name if sale.agent else sale.customer_name
                        ),
                        "seller": sale.seller.name,
                        "ticket_purchase": purchase_info,
                        "quantity": sale.quantity,
                        "unit_price": formatted_unit_price,
                        "total_price": formatted_total_price,
                        "profit": formatted_profit,
                        "currency": sale.currency,
                    },
                }
            )

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
