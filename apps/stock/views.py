from django.shortcuts import render
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Q
from datetime import timedelta
from .models import Supplier, TicketPurchase


class TicketPurchaseListView(LoginRequiredMixin, ListView):
    model = TicketPurchase
    template_name = "stock/ticket_purchase_list.html"
    context_object_name = "purchases"
    paginate_by = 10

    def get_queryset(self):
        queryset = TicketPurchase.objects.all().select_related("supplier")

        # Search functionality
        search_query = self.request.GET.get("search", "")
        if search_query:
            queryset = queryset.filter(
                Q(purchase_id__icontains=search_query)
                | Q(supplier__name__icontains=search_query)
                | Q(commentary__icontains=search_query)
            )

        # Date filtering
        date_filter = self.request.GET.get("date_filter", "today")
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

        if date_filter == "today":
            queryset = queryset.filter(purchase_date__gte=today)
        elif date_filter == "week":
            start_of_week = today - timedelta(days=today.weekday())
            queryset = queryset.filter(purchase_date__gte=start_of_week)
        elif date_filter == "month":
            start_of_month = today.replace(day=1)
            queryset = queryset.filter(purchase_date__gte=start_of_month)
        elif date_filter == "custom":
            start_date = self.request.GET.get("start_date")
            end_date = self.request.GET.get("end_date")
            if start_date and end_date:
                queryset = queryset.filter(
                    purchase_date__gte=start_date,
                    purchase_date__lte=end_date + " 23:59:59",
                )

        # Supplier filtering
        supplier_id = self.request.GET.get("supplier")
        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)

        # Currency filtering
        currency = self.request.GET.get("currency")
        if currency:
            queryset = queryset.filter(currency=currency)

        # Sorting
        sort_by = self.request.GET.get("sort_by", "-purchase_date")
        queryset = queryset.order_by(sort_by)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add filters to context
        context["search_query"] = self.request.GET.get("search", "")
        context["date_filter"] = self.request.GET.get("date_filter", "today")
        context["supplier_id"] = self.request.GET.get("supplier", "")
        context["currency"] = self.request.GET.get("currency", "")
        context["sort_by"] = self.request.GET.get("sort_by", "-purchase_date")

        # Add suppliers for filter dropdown
        context["suppliers"] = Supplier.objects.all()

        # Keep track of applied filters for clearing
        active_filters = {}
        for key, value in self.request.GET.items():
            if key != "page" and value:  # Exclude pagination parameter
                active_filters[key] = value
        context["active_filters"] = active_filters

        return context

    @property
    def total_price(self):
        return self.quantity * self.unit_price
