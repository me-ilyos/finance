from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views import View
from django.views.generic import ListView
from django.contrib import messages
from django.urls import reverse_lazy
from django.db.models import Q, Count, Sum, Case, When, Value, DecimalField
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import transaction
from .forms import LoginForm, SalespersonForm
from .models import Salesperson
from apps.sales.models import Sale
from .services import DateFilterService
from .dashboard_service import DashboardService
from .utils import ExcelExportService
from apps.accounting.models import FinancialAccount
import logging

logger = logging.getLogger(__name__)

# Create your views here.

class LoginView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('core:dashboard')
        form = LoginForm()
        return render(request, 'login.html', {'form': form})

    def post(self, request):
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('core:dashboard')
            else:
                form.add_error(None, "Foydalanuvchi nomi yoki parol noto'g'ri.")
        return render(request, 'login.html', {'form': form})


class SalespersonListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Salesperson
    template_name = 'core/salesperson_list.html'
    context_object_name = 'salespeople'
    paginate_by = 20
    login_url = '/core/login/'

    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        return self._get_filtered_queryset()

    def _get_filtered_queryset(self):
        """Centralized queryset filtering to avoid duplication"""
        queryset = self.model.objects.select_related('user').order_by('-created_at')
        
        # Apply date filtering for sales statistics
        try:
            start_date, end_date = DateFilterService.get_date_range(
                self.request.GET.get('filter_period'),
                self.request.GET.get('date_filter'),
                self.request.GET.get('start_date'),
                self.request.GET.get('end_date')
            )
            
            # Store date range for context
            self.sales_start_date = start_date
            self.sales_end_date = end_date
            
            # Annotate with sales statistics for the filtered period
            queryset = queryset.annotate(
                total_sales_count=Count(
                    'sales_made',
                    filter=Q(sales_made__sale_date__date__range=[start_date, end_date])
                ),
                total_sales_uzs=Sum(
                    Case(
                        When(
                            sales_made__sale_date__date__range=[start_date, end_date],
                            sales_made__sale_currency='UZS',
                            then='sales_made__total_sale_amount'
                        ),
                        default=Value(0),
                        output_field=DecimalField()
                    )
                ),
                total_sales_usd=Sum(
                    Case(
                        When(
                            sales_made__sale_date__date__range=[start_date, end_date],
                            sales_made__sale_currency='USD',
                            then='sales_made__total_sale_amount'
                        ),
                        default=Value(0),
                        output_field=DecimalField()
                    )
                )
            )
        except ValueError as e:
            logger.warning(f"Date filter error: {e}")
            today = timezone.localdate()
            self.sales_start_date = self.sales_end_date = today
            queryset = queryset.annotate(
                total_sales_count=Value(0),
                total_sales_uzs=Value(0),
                total_sales_usd=Value(0)
            )
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if 'salesperson_form' not in context:
            context['salesperson_form'] = SalespersonForm()
        
        # Use the service to get filter context
        filter_context = DateFilterService.get_filter_context(
            self.request.GET.get('filter_period'),
            self.request.GET.get('date_filter'),
            self.request.GET.get('start_date'),
            self.request.GET.get('end_date')
        )
        context.update(filter_context)

        # Calculate statistics for salespeople
        filtered_queryset = self.get_queryset()
        
        # Calculate totals for the footer
        total_sales_uzs = sum(sp.total_sales_uzs or 0 for sp in filtered_queryset)
        total_sales_usd = sum(sp.total_sales_usd or 0 for sp in filtered_queryset)
        total_sales_count = sum(sp.total_sales_count or 0 for sp in filtered_queryset)
        
        stats = {
            'total_salespeople': filtered_queryset.count(),
            'active_salespeople': filtered_queryset.filter(is_active=True).count(),
            'inactive_salespeople': filtered_queryset.filter(is_active=False).count(),
            'total_sales_uzs': total_sales_uzs,
            'total_sales_usd': total_sales_usd,
            'total_sales_count': total_sales_count,
        }
        context['stats'] = stats
        
        # Add sales date range to context for display
        context['sales_date_range'] = f"{self.sales_start_date.strftime('%d.%m.%Y')} - {self.sales_end_date.strftime('%d.%m.%Y')}"
        
        # Preserve query parameters for pagination
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            del query_params['page']
        context['query_params'] = query_params.urlencode()
        
        return context

    def post(self, request, *args, **kwargs):
        """Handle salesperson creation with business logic"""
        form = SalespersonForm(request.POST)
        if form.is_valid():
            try:
                salesperson = self._create_salesperson(form)
                if salesperson:
                    messages.success(request, "Yangi sotuvchi muvaffaqiyatli qo'shildi.")
                    return redirect(reverse_lazy('core:salesperson-list'))
                else:
                    messages.error(request, "Sotuvchini saqlashda xatolik yuz berdi.")
            except Exception as e:
                messages.error(request, f"Sotuvchini saqlashda xatolik: {e}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")

        # Re-render with form errors
        self.object_list = self.get_queryset()
        context = self.get_context_data(salesperson_form=form, object_list=self.object_list)
        
        if not messages.get_messages(request):
            messages.error(request, "Sotuvchini qo'shishda xatolik. Iltimos, ma'lumotlarni tekshiring.")
        
        return self.render_to_response(context)

    def _create_salesperson(self, form):
        """Create salesperson with business logic (moved from form)"""
        try:
            with transaction.atomic():
                # Create user
                user = User.objects.create_user(
                    username=form.cleaned_data['username'],
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    email=form.cleaned_data.get('email', ''),
                    password=form.cleaned_data['password']
                )
                
                # Create salesperson
                salesperson = Salesperson.objects.create(
                    user=user,
                    phone_number=form.cleaned_data.get('phone_number', ''),
                    is_active=form.cleaned_data.get('is_active', True)
                )
                
                return salesperson
        except Exception as e:
            logger.error(f"Error creating salesperson: {e}")
            raise


@login_required
def dashboard_view(request):
    """Dashboard view with business logic moved from service"""
    selected_account = None
    selected_account_id = request.GET.get('account_id')

    if selected_account_id:
        try:
            selected_account = get_object_or_404(
                FinancialAccount, 
                id=selected_account_id, 
                is_active=True
            )
        except FinancialAccount.DoesNotExist:
            messages.error(request, "Tanlangan hisob topilmadi.")
            return redirect('core:dashboard')

    # Get active accounts
    accounts = FinancialAccount.objects.filter(is_active=True)
    
    # Get transactions with pagination
    transactions_page = request.GET.get('page', 1)
    transactions_per_page = 10
    
    if selected_account:
        all_transactions = DashboardService.get_account_transactions(selected_account)
    else:
        all_transactions = DashboardService.get_recent_all_transactions()
    
    transactions_paginator = Paginator(all_transactions, transactions_per_page)
    transactions_page_obj = transactions_paginator.get_page(transactions_page)
    transactions = transactions_page_obj.object_list
    
    # Calculate statistics
    stats = DashboardService.calculate_account_statistics(accounts)
    
    context = {
        'accounts': accounts,
        'selected_account': selected_account,
        'transactions': transactions,
        'transactions_paginator': transactions_paginator,
        'transactions_page_obj': transactions_page_obj,
        'stats': stats,
        'page_title': 'Boshqaruv Paneli'
    }
    
    return render(request, 'core/dashboard.html', context)





@login_required
def logout_view(request):
    logout(request)
    return redirect('core:login')


@login_required
def salesperson_export_excel(request):
    """Export salesperson data to Excel format"""
    if not request.user.is_superuser:
        messages.error(request, "Bu funktsiyaga faqat administratorlar kirish huquqiga ega.")
        return redirect('core:salesperson-list')
    
    try:
        # Get the same queryset as the list view
        queryset = Salesperson.objects.select_related('user').order_by('-created_at')
        
        # Apply the same filtering as the list view
        try:
            start_date_obj, end_date_obj = DateFilterService.get_date_range(
                request.GET.get('filter_period'),
                request.GET.get('date_filter'),
                request.GET.get('start_date'),
                request.GET.get('end_date')
            )
        except ValueError:
            today = timezone.localdate()
            start_date_obj = end_date_obj = today
        
        # Annotate with sales statistics for the filtered period
        queryset = queryset.annotate(
            total_sales_count=Count(
                'sales_made',
                filter=Q(sales_made__sale_date__date__range=[start_date_obj, end_date_obj])
            ),
            total_sales_uzs=Sum(
                Case(
                    When(
                        sales_made__sale_date__date__range=[start_date_obj, end_date_obj],
                        sales_made__sale_currency='UZS',
                        then='sales_made__total_sale_amount'
                    ),
                    default=Value(0),
                    output_field=DecimalField()
                )
            ),
            total_sales_usd=Sum(
                Case(
                    When(
                        sales_made__sale_date__date__range=[start_date_obj, end_date_obj],
                        sales_made__sale_currency='USD',
                        then='sales_made__total_sale_amount'
                    ),
                    default=Value(0),
                    output_field=DecimalField()
                )
            )
        )

        # Use ExcelExportService to generate the Excel file
        return ExcelExportService.export_salespeople(queryset, start_date_obj, end_date_obj)
        
    except Exception as e:
        logger.error(f"Error exporting salespeople to Excel: {e}")
        messages.error(request, "Excel faylini eksport qilishda xatolik yuz berdi.")
        return redirect('core:salesperson-list')


@login_required
def salesperson_edit(request, salesperson_id):
    """Edit salesperson details"""
    if not request.user.is_superuser:
        messages.error(request, "Bu funktsiyaga faqat administratorlar kirish huquqiga ega.")
        return redirect('core:salesperson-list')
    
    try:
        salesperson = get_object_or_404(Salesperson, id=salesperson_id)
        
        if request.method == 'POST':
            # Get form data
            username = request.POST.get('username', '').strip()
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip()
            phone_number = request.POST.get('phone_number', '').strip()
            is_active = request.POST.get('is_active') == 'on'
            password = request.POST.get('password', '').strip()
            password_confirm = request.POST.get('password_confirm', '').strip()
            
            # Basic validation
            if not username or not first_name or not last_name:
                messages.error(request, "Majburiy maydonlarni to'ldiring.")
                return redirect('core:salesperson-list')
            
            # Password validation
            if password or password_confirm:
                if not password:
                    messages.error(request, "Parol maydonini to'ldiring.")
                    return redirect('core:salesperson-list')
                if password != password_confirm:
                    messages.error(request, "Parollar mos kelmadi.")
                    return redirect('core:salesperson-list')
                if len(password) < 8:
                    messages.error(request, "Parol kamida 8 ta belgidan iborat bo'lishi kerak.")
                    return redirect('core:salesperson-list')
            
            # Check username uniqueness
            if User.objects.filter(username=username).exclude(id=salesperson.user.id).exists():
                messages.error(request, "Bu foydalanuvchi nomi allaqachon mavjud.")
                return redirect('core:salesperson-list')
            
            try:
                with transaction.atomic():
                    # Update user fields
                    user = salesperson.user
                    user.username = username
                    user.first_name = first_name
                    user.last_name = last_name
                    user.email = email
                    
                    if password:
                        user.set_password(password)
                    
                    user.save()
                    
                    # Update salesperson fields
                    salesperson.phone_number = phone_number
                    salesperson.is_active = is_active
                    salesperson.save()
                    
                    messages.success(request, "Sotuvchi ma'lumotlari muvaffaqiyatli yangilandi.")
                    
            except Exception as e:
                logger.error(f"Error updating salesperson: {e}")
                messages.error(request, "Ma'lumotlarni yangilashda xatolik yuz berdi.")
        
    except Exception as e:
        logger.error(f"Error in salesperson_edit: {e}")
        messages.error(request, "Xatolik yuz berdi.")
    
    return redirect('core:salesperson-list')


@login_required  
def salesperson_toggle_status(request, salesperson_id):
    """Toggle salesperson active status"""
    if not request.user.is_superuser:
        messages.error(request, "Bu funktsiyaga faqat administratorlar kirish huquqiga ega.")
        return redirect('core:salesperson-list')
    
    try:
        salesperson = get_object_or_404(Salesperson, id=salesperson_id)
        salesperson.is_active = not salesperson.is_active
        salesperson.save()
        
        status = "faollashtirildi" if salesperson.is_active else "faolsizlashtirildi"
        messages.success(request, f"Sotuvchi muvaffaqiyatli {status}.")
        
    except Exception as e:
        logger.error(f"Error toggling salesperson status: {e}")
        messages.error(request, "Sotuvchi holatini o'zgartirishda xatolik yuz berdi.")
    
    return redirect('core:salesperson-list')


class SalespersonDetailView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Sale
    template_name = 'core/salesperson_detail.html'
    context_object_name = 'sales'
    paginate_by = 20
    login_url = '/core/login/'

    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        return self._get_filtered_queryset()

    def _get_filtered_queryset(self):
        """Centralized queryset filtering"""
        self.salesperson = get_object_or_404(Salesperson, pk=self.kwargs['salesperson_id'])
        
        queryset = Sale.objects.filter(salesperson=self.salesperson).select_related(
            'related_acquisition__ticket',
            'agent',
            'paid_to_account'
        ).order_by('-sale_date')
        
        # Apply date filtering
        try:
            start_date, end_date = DateFilterService.get_date_range(
                self.request.GET.get('filter_period'),
                self.request.GET.get('date_filter'),
                self.request.GET.get('start_date'),
                self.request.GET.get('end_date')
            )
            queryset = queryset.filter(sale_date__date__range=[start_date, end_date])
        except ValueError as e:
            logger.warning(f"Date filter error: {e}")
            today = timezone.localdate()
            queryset = queryset.filter(sale_date__date=today)
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['salesperson'] = self.salesperson
        
        # Use service to get filter context
        filter_context = DateFilterService.get_filter_context(
            self.request.GET.get('filter_period'),
            self.request.GET.get('date_filter'),
            self.request.GET.get('start_date'),
            self.request.GET.get('end_date')
        )
        context.update(filter_context)
        
        # Calculate totals for filtered sales
        filtered_sales = self.get_queryset()
        stats = {
            'total_sales': filtered_sales.count(),
            'total_quantity': sum(sale.quantity for sale in filtered_sales),
            'total_amount_uzs': sum(sale.total_sale_amount for sale in filtered_sales if sale.sale_currency == 'UZS'),
            'total_amount_usd': sum(sale.total_sale_amount for sale in filtered_sales if sale.sale_currency == 'USD'),
            'total_profit_uzs': sum(sale.profit for sale in filtered_sales if sale.sale_currency == 'UZS'),
            'total_profit_usd': sum(sale.profit for sale in filtered_sales if sale.sale_currency == 'USD'),
        }
        context['stats'] = stats
        
        # Preserve query parameters for pagination
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            del query_params['page']
        context['query_params'] = query_params.urlencode()
        
        return context
