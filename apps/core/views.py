from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views import View
from django.contrib import messages
from .forms import LoginForm
from .services import DashboardService
from apps.accounting.models import FinancialAccount

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

@login_required
def dashboard_view(request):
    """Dashboard view using service layer for data aggregation"""
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

    # Get pagination parameters
    transactions_page = request.GET.get('page', 1)
    transactions_per_page = 10

    # Get dashboard data using service
    dashboard_data = DashboardService.get_dashboard_data(
        selected_account, 
        transactions_page, 
        transactions_per_page
    )
    
    context = {
        **dashboard_data,
        'page_title': 'Boshqaruv Paneli'
    }
    
    return render(request, 'core/dashboard.html', context)

@login_required
def logout_view(request):
    logout(request)
    return redirect('core:login')
