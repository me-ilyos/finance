from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.contrib.auth import logout
from django.contrib import messages
from django.views.generic import ListView, DetailView
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.http import JsonResponse
from django.urls import reverse, reverse_lazy
from django.db.models import Q
from datetime import timedelta
from .models import Supplier, TicketPurchase
import json
from decimal import Decimal
import decimal
from .utils import AdminRequiredMixin, is_admin


# Authentication views
class CustomLoginView(LoginView):
    template_name = 'login.html'
    redirect_authenticated_user = True
    
    def form_valid(self, form):
        """Validate the user is staff/admin"""
        user = form.get_user()
        # Check if the user is either staff or superuser
        if not (user.is_staff or user.is_superuser):
            form.add_error(None, "Access restricted to admin users only.")
            messages.error(self.request, "Access restricted to admin users only.")
            return self.form_invalid(form)
        
        messages.success(self.request, f"Welcome back, {user.username}!")
        return super().form_valid(form)
    
    def get_success_url(self):
        """Return the dashboard url"""
        return reverse_lazy('finance:sale_list')

@login_required
def logout_view(request):
    logout(request)
    messages.success(request, "You have been successfully logged out.")
    return redirect('login')

class TicketPurchaseListView(AdminRequiredMixin, LoginRequiredMixin, ListView):
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

        # --- Add data for JavaScript ---
        js_suppliers = list(Supplier.objects.values('id', 'name')) # Prepare suppliers for JSON
        js_data = {
            'suppliers': js_suppliers,
            'purchase_create_url': reverse('stock:purchase_create') # Add the URL for the create view
        }
        context['js_data'] = json.dumps(js_data) # Convert to JSON string
        # --- End Add data for JavaScript ---

        return context

    @property
    def total_price(self):
        return self.quantity * self.unit_price


@login_required
@user_passes_test(is_admin, login_url=reverse_lazy('login'))
@require_POST
def purchase_create(request):
    """Handle the AJAX form submission for creating a new ticket purchase"""
    # Check for AJAX request
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        try:
            # Extract form data
            supplier_id = request.POST.get("supplier")
            purchase_date_str = request.POST.get("purchase_date")
            quantity = request.POST.get("quantity")
            unit_price = request.POST.get("unit_price")
            currency = request.POST.get("currency")
            flight_details = request.POST.get("flight_details", "")
            notes = request.POST.get("notes", "")

            # --- Validation --- 
            if not all([supplier_id, quantity, unit_price, currency]):
                return JsonResponse({"success": False, "errors": "Missing required fields."}, status=400)
            
            # Convert string values to appropriate types
            try:
                quantity = int(quantity)
                unit_price = Decimal(unit_price)
            except (ValueError, decimal.InvalidOperation):
                return JsonResponse({"success": False, "errors": "Invalid quantity or price."}, status=400)
            
            if quantity <= 0:
                return JsonResponse({"success": False, "errors": "Quantity must be positive."}, status=400)
                
            if unit_price <= 0:
                return JsonResponse({"success": False, "errors": "Price must be positive."}, status=400)
            
            # Get the related Supplier object
            try:
                supplier = Supplier.objects.get(id=supplier_id)
            except Supplier.DoesNotExist:
                return JsonResponse({"success": False, "errors": "Invalid Supplier."}, status=400)
            
            # Convert purchase_date string to a datetime object
            from django.utils.dateparse import parse_datetime
            purchase_date = parse_datetime(purchase_date_str) if purchase_date_str else timezone.now()

            # Create the purchase
            purchase = TicketPurchase.objects.create(
                supplier=supplier,
                purchase_date=purchase_date,
                quantity=quantity,
                unit_price=unit_price,
                currency=currency,
                flight_details=flight_details,
                notes=notes,
            )

            # Prepare response data
            return JsonResponse({
                "success": True,
                "purchase": {
                    "id": purchase.id,
                    "purchase_id": purchase.purchase_id,
                    "purchase_date": purchase.purchase_date.strftime("%b %d, %Y"),
                    "supplier": supplier.name,
                    "quantity": purchase.quantity,
                    "quantity_sold": 0,
                    "quantity_remaining": purchase.quantity,
                    "unit_price": float(purchase.unit_price),
                    "currency": purchase.currency,
                }
            })
        except Exception as e:
            import traceback
            return JsonResponse(
                {
                    "success": False, 
                    "errors": str(e),
                    "traceback": traceback.format_exc()
                }, 
                status=400
            )

    return JsonResponse({"success": False, "errors": "Invalid request"}, status=400)

# Apply the admin check to function-based views (decorator)
@login_required
@user_passes_test(is_admin, login_url=reverse_lazy('login'))
def some_view(request):
    # Example of how to use the decorator
    pass
