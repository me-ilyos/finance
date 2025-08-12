from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views import View
from django.views.generic import ListView
from django.urls import reverse_lazy
from django.db.models import Q, Count, Sum, Case, When, Value, DecimalField
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .forms import LoginForm, SalespersonForm
from .models import Salesperson
from apps.sales.models import Sale
from .services import DateFilterService
from .dashboard_service import DashboardService
from .utils import ExcelExportService
from apps.accounting.models import FinancialAccount, Transfer
from apps.accounting.forms import TransferForm, DepositForm


class LoginView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('core:dashboard')
        return render(request, 'login.html', {'form': LoginForm()})

    def post(self, request):
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                request, 
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password']
            )
            if user:
                login(request, user)
                return redirect('core:dashboard')
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
        queryset = self.model.objects.select_related('user').order_by('-created_at')
        
        try:
            start_date, end_date = DateFilterService.get_date_range(
                self.request.GET.get('filter_period'),
                self.request.GET.get('date_filter'),
                self.request.GET.get('start_date'),
                self.request.GET.get('end_date')
            )
            
            self.sales_start_date = start_date
            self.sales_end_date = end_date
            
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
                ),
                total_commission_uzs=Sum(
                    Case(
                        When(
                            acquisitions_made__commissions__commission_date__date__range=[start_date, end_date],
                            acquisitions_made__commissions__currency='UZS',
                            then='acquisitions_made__commissions__amount'
                        ),
                        default=Value(0),
                        output_field=DecimalField()
                    ),
                    distinct=True
                ),
                total_commission_usd=Sum(
                    Case(
                        When(
                            acquisitions_made__commissions__commission_date__date__range=[start_date, end_date],
                            acquisitions_made__commissions__currency='USD',
                            then='acquisitions_made__commissions__amount'
                        ),
                        default=Value(0),
                        output_field=DecimalField()
                    ),
                    distinct=True
                )
            )
        except ValueError:
            today = timezone.localdate()
            self.sales_start_date = self.sales_end_date = today
            queryset = queryset.annotate(
                total_sales_count=Value(0),
                total_sales_uzs=Value(0),
                total_sales_usd=Value(0),
                total_commission_uzs=Value(0),
                total_commission_usd=Value(0)
            )
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if 'salesperson_form' not in context:
            context['salesperson_form'] = SalespersonForm()
        
        filter_context = DateFilterService.get_filter_context(
            self.request.GET.get('filter_period'),
            self.request.GET.get('date_filter'),
            self.request.GET.get('start_date'),
            self.request.GET.get('end_date')
        )
        context.update(filter_context)

        filtered_queryset = self.get_queryset()
        
        total_sales_uzs = sum(sp.total_sales_uzs or 0 for sp in filtered_queryset)
        total_sales_usd = sum(sp.total_sales_usd or 0 for sp in filtered_queryset)
        total_sales_count = sum(sp.total_sales_count or 0 for sp in filtered_queryset)
        total_commission_uzs = sum(sp.total_commission_uzs or 0 for sp in filtered_queryset)
        total_commission_usd = sum(sp.total_commission_usd or 0 for sp in filtered_queryset)
        
        context['stats'] = {
            'total_salespeople': filtered_queryset.count(),
            'active_salespeople': filtered_queryset.filter(is_active=True).count(),
            'inactive_salespeople': filtered_queryset.filter(is_active=False).count(),
            'total_sales_uzs': total_sales_uzs,
            'total_sales_usd': total_sales_usd,
            'total_sales_count': total_sales_count,
            'total_commission_uzs': total_commission_uzs,
            'total_commission_usd': total_commission_usd,
        }
        
        context['sales_date_range'] = f"{self.sales_start_date.strftime('%d.%m.%Y')} - {self.sales_end_date.strftime('%d.%m.%Y')}"
        
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            del query_params['page']
        context['query_params'] = query_params.urlencode()
        
        return context

    def post(self, request, *args, **kwargs):
        form = SalespersonForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=form.cleaned_data['username'],
                        first_name=form.cleaned_data['first_name'],
                        last_name=form.cleaned_data['last_name'],
                        email=form.cleaned_data.get('email', ''),
                        password=form.cleaned_data['password']
                    )
                    
                    Salesperson.objects.create(
                        user=user,
                        phone_number=form.cleaned_data.get('phone_number', ''),
                        is_active=form.cleaned_data.get('is_active', True)
                    )
                return redirect(reverse_lazy('core:salesperson-list'))
            except:
                pass

        self.object_list = self.get_queryset()
        context = self.get_context_data(salesperson_form=form, object_list=self.object_list)
        return self.render_to_response(context)


@login_required
def dashboard_view(request):
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
            return redirect('core:dashboard')

    accounts = FinancialAccount.objects.filter(is_active=True)
    
    transactions_page = request.GET.get('page', 1)
    transactions_per_page = 10
    
    if selected_account:
        all_transactions = DashboardService.get_account_transactions(selected_account)
    else:
        all_transactions = DashboardService.get_recent_all_transactions()
    
    transactions_paginator = Paginator(all_transactions, transactions_per_page)
    transactions_page_obj = transactions_paginator.get_page(transactions_page)
    transactions = transactions_page_obj.object_list
    
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
    if not request.user.is_superuser:
        return redirect('core:salesperson-list')
    
    try:
        queryset = Salesperson.objects.select_related('user').order_by('-created_at')
        
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
            ),
            total_commission_uzs=Sum(
                Case(
                    When(
                        acquisitions_made__commissions__commission_date__date__range=[start_date_obj, end_date_obj],
                        acquisitions_made__commissions__currency='UZS',
                        then='acquisitions_made__commissions__amount'
                    ),
                    default=Value(0),
                    output_field=DecimalField()
                ),
                distinct=True
            ),
            total_commission_usd=Sum(
                Case(
                    When(
                        acquisitions_made__commissions__commission_date__date__range=[start_date_obj, end_date_obj],
                        acquisitions_made__commissions__currency='USD',
                        then='acquisitions_made__commissions__amount'
                    ),
                    default=Value(0),
                    output_field=DecimalField()
                ),
                distinct=True
            )
        )

        return ExcelExportService.export_salespeople(queryset, start_date_obj, end_date_obj)
        
    except:
        return redirect('core:salesperson-list')


@login_required
def salesperson_edit(request, salesperson_id):
    if not request.user.is_superuser:
        return redirect('core:salesperson-list')
    
    try:
        salesperson = get_object_or_404(Salesperson, id=salesperson_id)
        
        if request.method == 'POST':
            username = request.POST.get('username', '').strip()
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip()
            phone_number = request.POST.get('phone_number', '').strip()
            is_active = request.POST.get('is_active') == 'on'
            password = request.POST.get('password', '').strip()
            password_confirm = request.POST.get('password_confirm', '').strip()
            
            if not username or not first_name or not last_name:
                return redirect('core:salesperson-list')
            
            if password or password_confirm:
                if not password or password != password_confirm or len(password) < 8:
                    return redirect('core:salesperson-list')
            
            if User.objects.filter(username=username).exclude(id=salesperson.user.id).exists():
                return redirect('core:salesperson-list')
            
            try:
                with transaction.atomic():
                    user = salesperson.user
                    user.username = username
                    user.first_name = first_name
                    user.last_name = last_name
                    user.email = email
                    
                    if password:
                        user.set_password(password)
                    
                    user.save()
                    
                    salesperson.phone_number = phone_number
                    salesperson.is_active = is_active
                    salesperson.save()
                    
            except:
                pass
        
    except:
        pass
    
    return redirect('core:salesperson-list')


@login_required  
def salesperson_toggle_status(request, salesperson_id):
    if not request.user.is_superuser:
        return redirect('core:salesperson-list')
    
    try:
        salesperson = get_object_or_404(Salesperson, id=salesperson_id)
        salesperson.is_active = not salesperson.is_active
        salesperson.save()
    except:
        pass
    
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
        self.salesperson = get_object_or_404(Salesperson, pk=self.kwargs['pk'])
        
        queryset = Sale.objects.filter(salesperson=self.salesperson).select_related(
            'related_acquisition__ticket',
            'agent',
            'paid_to_account'
        ).order_by('-sale_date')
        
        try:
            start_date, end_date = DateFilterService.get_date_range(
                self.request.GET.get('filter_period'),
                self.request.GET.get('date_filter'),
                self.request.GET.get('start_date'),
                self.request.GET.get('end_date')
            )
            queryset = queryset.filter(sale_date__date__range=[start_date, end_date])
        except ValueError:
            today = timezone.localdate()
            queryset = queryset.filter(sale_date__date=today)
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['salesperson'] = self.salesperson
        
        filter_context = DateFilterService.get_filter_context(
            self.request.GET.get('filter_period'),
            self.request.GET.get('date_filter'),
            self.request.GET.get('start_date'),
            self.request.GET.get('end_date')
        )
        context.update(filter_context)
        
        filtered_sales = self.get_queryset()
        context['stats'] = {
            'total_sales': filtered_sales.count(),
            'total_quantity': sum(sale.quantity for sale in filtered_sales),
            'total_amount_uzs': sum(sale.total_sale_amount for sale in filtered_sales if sale.sale_currency == 'UZS'),
            'total_amount_usd': sum(sale.total_sale_amount for sale in filtered_sales if sale.sale_currency == 'USD'),
            'total_profit_uzs': sum(sale.profit for sale in filtered_sales if sale.sale_currency == 'UZS'),
            'total_profit_usd': sum(sale.profit for sale in filtered_sales if sale.sale_currency == 'USD'),
        }
        
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            del query_params['page']
        context['query_params'] = query_params.urlencode()
        
        return context


@require_http_methods(["POST"])
@login_required
def transfer_money(request):
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Bu funktsiyaga faqat administratorlar kirish huquqiga ega.'}, status=403)
    
    try:
        form = TransferForm(request.POST)
        
        if form.is_valid():
            try:
                transfer = form.save()
                return JsonResponse({
                    'success': True,
                    'message': 'Mablag\' muvaffaqiyatli o\'tkazildi.',
                    'transfer_id': transfer.id
                })
            except Exception as save_error:
                return JsonResponse({
                    'success': False,
                    'error': f'Transfer saqlashda xatolik: {str(save_error)}'
                }, status=500)
        else:
            errors = []
            for field, field_errors in form.errors.items():
                for error in field_errors:
                    if field == '__all__':
                        errors.append(str(error))
                    else:
                        field_label = form.fields.get(field, {}).label or field
                        errors.append(f"{field_label}: {error}")
            
            return JsonResponse({
                'success': False,
                'errors': errors
            }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Kutilmagan xatolik: {str(e)}'
        }, status=500)


@login_required
def get_transfer_form(request):
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Bu funktsiyaga faqat administratorlar kirish huquqiga ega.'}, status=403)
    
    accounts = FinancialAccount.objects.filter(is_active=True)
    account_options = []
    
    for account in accounts:
        account_options.append({
            'id': account.id,
            'name': account.name,
            'currency': account.currency,
            'balance': float(account.current_balance),
            'formatted_balance': f"{account.current_balance:,.2f} {account.currency}"
        })
    
    return JsonResponse({'accounts': account_options})


@require_http_methods(["POST"])
@login_required
def deposit_money(request):
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Bu funktsiyaga faqat administratorlar kirish huquqiga ega.'}, status=403)

    try:
        form = DepositForm(request.POST)
        if form.is_valid():
            try:
                deposit = form.save()
                return JsonResponse({
                    'success': True,
                    'message': "Kirim muvaffaqiyatli qo'shildi.",
                    'deposit_id': deposit.id
                })
            except Exception as save_error:
                return JsonResponse({
                    'success': False,
                    'error': f"Kirim saqlashda xatolik: {str(save_error)}"
                }, status=500)
        else:
            errors = []
            for field, field_errors in form.errors.items():
                for error in field_errors:
                    if field == '__all__':
                        errors.append(str(error))
                    else:
                        field_label = form.fields.get(field, {}).label or field
                        errors.append(f"{field_label}: {error}")
            return JsonResponse({'success': False, 'errors': errors}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Kutilmagan xatolik: {str(e)}'}, status=500)
