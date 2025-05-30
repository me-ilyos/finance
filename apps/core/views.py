from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views import View
from django.utils import timezone
from decimal import Decimal
from .forms import LoginForm
from apps.accounting.models import FinancialAccount, Expenditure
from apps.sales.models import Sale
# Potentially Acquisition if payments are tracked to accounts directly
# from apps.inventory.models import Acquisition, AcquisitionPayment # Assuming AcquisitionPayment model exists and links to FinancialAccount

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
    accounts = FinancialAccount.objects.filter(is_active=True)
    selected_account_id = request.GET.get('account_id')
    selected_account = None
    transactions = []

    if selected_account_id:
        try:
            selected_account = FinancialAccount.objects.get(id=selected_account_id, is_active=True)
            
            # Fetch sales paid to this account
            sales_to_account = Sale.objects.filter(paid_to_account=selected_account).select_related(
                'agent', 'related_acquisition__ticket'
            )
            for sale in sales_to_account:
                transactions.append({
                    'date': sale.sale_date,
                    'type': 'Sotuv',
                    'description': f"{sale.related_acquisition.ticket.get_ticket_type_display()} - {sale.related_acquisition.ticket.description} - {sale.agent.name if sale.agent else sale.client_full_name}",
                    'amount': sale.paid_amount_on_this_sale if sale.agent else sale.total_sale_amount, # Consider initial for agent, full for client
                    'currency': sale.sale_currency,
                    'balance_effect': 'income'
                })

            # Fetch expenditures from this account
            expenditures_from_account = Expenditure.objects.filter(paid_from_account=selected_account)
            for exp in expenditures_from_account:
                transactions.append({
                    'date': exp.expenditure_date,
                    'type': 'Xarajat',
                    'description': exp.description,
                    'amount': exp.amount,
                    'currency': exp.currency,
                    'balance_effect': 'expense'
                })
            
            # TODO: Add AcquisitionPayments if they directly debit FinancialAccount
            # Example:
            # acquisition_payments = AcquisitionPayment.objects.filter(paid_from_account=selected_account)
            # for acq_payment in acquisition_payments:
            #     transactions.append({
            #         'date': acq_payment.payment_date,
            #         'type': 'Xarid To'lovi',
            #         'description': f"Supplier: {acq_payment.acquisition.supplier.name} - {acq_payment.acquisition.ticket.short_description()}",
            #         'amount': acq_payment.amount,
            #         'currency': acq_payment.currency,
            #         'balance_effect': 'expense'
            #     })

            # Sort transactions by date, most recent first
            transactions.sort(key=lambda t: t['date'], reverse=True)

        except FinancialAccount.DoesNotExist:
            selected_account = None # Account not found or not active
            # Optionally add a message: messages.error(request, "Tanlangan hisob topilmadi.")

    context = {
        'accounts': accounts,
        'selected_account': selected_account,
        'transactions': transactions,
        'page_title': 'Boshqaruv Paneli'
    }
    return render(request, 'core/dashboard.html', context)

@login_required
def logout_view(request):
    logout(request)
    return redirect('core:login')
