from django.shortcuts import get_object_or_404, redirect
from django.views.generic import DetailView, CreateView
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect, JsonResponse
from django.db.models import Sum, Q
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages
import logging

from .models import Agent, Supplier, AgentPayment, SupplierPayment
from .forms import AgentForm, SupplierForm, AgentPaymentForm, SupplierPaymentForm

logger = logging.getLogger(__name__)


class AgentListView(CreateView):
    model = Agent
    form_class = AgentForm
    template_name = 'contacts/agent_list.html'
    success_url = reverse_lazy('contacts:agent-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['agents'] = Agent.objects.all().order_by('-created_at')
        return context

    def form_valid(self, form):
        try:
            form.save()
        except Exception as e:
            logger.error(f"Error creating Agent: {e}")
        return HttpResponseRedirect(self.success_url)


class SupplierListView(LoginRequiredMixin, CreateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'contacts/supplier_list.html'
    success_url = reverse_lazy('contacts:supplier-list')
    login_url = '/core/login/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Show only active suppliers
        context['suppliers'] = Supplier.objects.filter(is_active=True).order_by('-created_at')
        # Check if user can add suppliers (only admins)
        context['can_add_supplier'] = self.request.user.is_superuser
        return context

    def post(self, request, *args, **kwargs):
        # Only allow admins to create suppliers
        if not request.user.is_superuser:
            return redirect('contacts:supplier-list')
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            form.save()
        except Exception as e:
            logger.error(f"Error creating Supplier: {e}")
        return HttpResponseRedirect(self.success_url)


class SupplierDetailView(LoginRequiredMixin, DetailView):
    model = Supplier
    template_name = 'contacts/supplier_detail.html'
    login_url = '/core/login/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        supplier = self.object
        
        # Get filter parameter from request
        filter_type = self.request.GET.get('filter', 'all')
        page = self.request.GET.get('page', 1)
        
        # Get base querysets
        acquisitions = supplier.acquisitions.select_related('ticket').order_by('-acquisition_date')
        payments = supplier.payments.select_related('paid_from_account').order_by('-payment_date')
        
        # Apply filtering based on filter_type
        if filter_type == 'uzs':
            acquisitions = acquisitions.filter(currency='UZS')
            payments = payments.filter(currency='UZS')
        elif filter_type == 'usd':
            acquisitions = acquisitions.filter(currency='USD')
            payments = payments.filter(currency='USD')
        elif filter_type == 'umra':
            acquisitions = acquisitions.filter(ticket__ticket_type='UMRA')
            payments = payments.none()  # No payments are specific to ticket type
        
        # Create transactions list
        transactions = []
        for acq in acquisitions:
            transactions.append({'date': acq.acquisition_date, 'type': 'acquisition', 'acquisition': acq})
        for payment in payments:
            transactions.append({'date': payment.payment_date, 'type': 'payment', 'payment': payment})
        
        transactions.sort(key=lambda x: x['date'], reverse=True)
        
        # Paginate transactions
        paginator = Paginator(transactions, 20)  # 20 transactions per page
        try:
            paginated_transactions = paginator.page(page)
        except PageNotAnInteger:
            paginated_transactions = paginator.page(1)
        except EmptyPage:
            paginated_transactions = paginator.page(paginator.num_pages)
        
        # Calculate totals for display in table footer - respect current filter
        if filter_type == 'uzs':
            filtered_acquisitions = supplier.acquisitions.select_related('ticket').filter(currency='UZS')
            filtered_payments = supplier.payments.select_related('paid_from_account').filter(currency='UZS')
            
            uzs_acquisitions = filtered_acquisitions.aggregate(total=Sum('total_amount'))['total'] or 0
            uzs_payments = filtered_payments.aggregate(total=Sum('amount'))['total'] or 0
            usd_acquisitions = 0
            usd_payments = 0
            
            # Calculate filtered balance for UZS only
            filtered_balance_uzs = uzs_acquisitions - uzs_payments + (supplier.initial_balance_uzs or 0)
            filtered_balance_usd = 0
            
        elif filter_type == 'usd':
            filtered_acquisitions = supplier.acquisitions.select_related('ticket').filter(currency='USD')
            filtered_payments = supplier.payments.select_related('paid_from_account').filter(currency='USD')
            
            usd_acquisitions = filtered_acquisitions.aggregate(total=Sum('total_amount'))['total'] or 0
            usd_payments = filtered_payments.aggregate(total=Sum('amount'))['total'] or 0
            uzs_acquisitions = 0
            uzs_payments = 0
            
            # Calculate filtered balance for USD only
            filtered_balance_uzs = 0
            filtered_balance_usd = usd_acquisitions - usd_payments + (supplier.initial_balance_usd or 0)
            
        elif filter_type == 'umra':
            filtered_acquisitions = supplier.acquisitions.select_related('ticket').filter(ticket__ticket_type='UMRA')
            filtered_payments = supplier.payments.select_related('paid_from_account').none()  # No payments are specific to ticket type
            
            uzs_acquisitions = filtered_acquisitions.filter(currency='UZS').aggregate(total=Sum('total_amount'))['total'] or 0
            usd_acquisitions = filtered_acquisitions.filter(currency='USD').aggregate(total=Sum('total_amount'))['total'] or 0
            uzs_payments = 0
            usd_payments = 0
            
            # Calculate filtered balance for UMRA only (no initial balance included for ticket-type filters)
            filtered_balance_uzs = uzs_acquisitions - uzs_payments
            filtered_balance_usd = usd_acquisitions - usd_payments
            
        else:  # filter_type == 'all'
            filtered_acquisitions = supplier.acquisitions.select_related('ticket')
            filtered_payments = supplier.payments.select_related('paid_from_account')
            
            uzs_acquisitions = filtered_acquisitions.filter(currency='UZS').aggregate(total=Sum('total_amount'))['total'] or 0
            usd_acquisitions = filtered_acquisitions.filter(currency='USD').aggregate(total=Sum('total_amount'))['total'] or 0
            uzs_payments = filtered_payments.filter(currency='UZS').aggregate(total=Sum('amount'))['total'] or 0
            usd_payments = filtered_payments.filter(currency='USD').aggregate(total=Sum('amount'))['total'] or 0
            
            # Use actual supplier balance for 'all' filter
            filtered_balance_uzs = supplier.balance_uzs
            filtered_balance_usd = supplier.balance_usd
        
        context.update({
            'transactions': paginated_transactions,
            'acquisitions': supplier.acquisitions.select_related('ticket').order_by('-acquisition_date'),
            'payments': supplier.payments.select_related('paid_from_account').order_by('-payment_date'),
            'payment_form': SupplierPaymentForm(),
            'current_filter': filter_type,
            # Table footer totals (always show complete totals)
            'uzs_acquisitions': uzs_acquisitions,
            'usd_acquisitions': usd_acquisitions,
            'uzs_payments': uzs_payments,
            'usd_payments': usd_payments,
            'filtered_balance_uzs': filtered_balance_uzs,
            'filtered_balance_usd': filtered_balance_usd,
            # Check if user can deactivate (only admins)
            'can_deactivate': self.request.user.is_superuser,
        })
        return context


@login_required(login_url='/core/login/')
def deactivate_supplier(request, supplier_pk):
    """Deactivate supplier - only admins and only when there's no debt"""
    if not request.user.is_superuser:
        return JsonResponse({
            'success': False, 
            'message': "Faqat administratorlar ta'minotchini faolsizlashtira oladi."
        })
    
    try:
        supplier = get_object_or_404(Supplier, pk=supplier_pk)
        
        if not supplier.can_be_deactivated():
            return JsonResponse({
                'success': False,
                'message': "Ta'minotchini faolsizlashtirish uchun barcha qarzlar to'lanishi kerak (UZS va USD balans 0 bo'lishi kerak)."
            })
        
        supplier.is_active = False
        supplier.save(update_fields=['is_active', 'updated_at'])
        
        return JsonResponse({'success': True, 'message': "Ta'minotchi faolsizlashtirildi."})
        
    except Exception as e:
        logger.error(f"Error deactivating supplier: {e}")
        return JsonResponse({
            'success': False, 
            'message': "Ta'minotchini faolsizlashtirishda xatolik yuz berdi."
        })


class AgentDetailView(DetailView):
    model = Agent
    template_name = 'contacts/agent_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent = self.object
        
        # Get filter parameter from request
        filter_type = self.request.GET.get('filter', 'all')
        page = self.request.GET.get('page', 1)
        
        # Get base querysets
        sales = agent.agent_sales.select_related('related_acquisition__ticket').order_by('-sale_date')
        payments = agent.payments.select_related('paid_to_account').order_by('-payment_date')
        
        # Apply filtering based on filter_type
        if filter_type == 'uzs':
            sales = sales.filter(sale_currency='UZS')
            payments = payments.filter(currency='UZS')
        elif filter_type == 'usd':
            sales = sales.filter(sale_currency='USD')
            payments = payments.filter(currency='USD')
        elif filter_type == 'umra':
            sales = sales.filter(related_acquisition__ticket__ticket_type='UMRA')
            payments = payments.none()  # No payments are specific to ticket type
        
        # Create transactions list
        transactions = []
        for sale in sales:
            transactions.append({'date': sale.sale_date, 'type': 'sale', 'sale': sale})
        for payment in payments:
            transactions.append({'date': payment.payment_date, 'type': 'payment', 'payment': payment})
        
        transactions.sort(key=lambda x: x['date'], reverse=True)
        
        # Paginate transactions
        paginator = Paginator(transactions, 20)  # 20 transactions per page
        try:
            paginated_transactions = paginator.page(page)
        except PageNotAnInteger:
            paginated_transactions = paginator.page(1)
        except EmptyPage:
            paginated_transactions = paginator.page(paginator.num_pages)
        
        # Calculate totals for display in table footer - respect current filter
        if filter_type == 'uzs':
            filtered_sales = agent.agent_sales.select_related('related_acquisition__ticket').filter(sale_currency='UZS')
            filtered_payments = agent.payments.select_related('paid_to_account').filter(currency='UZS')
            
            uzs_sales = filtered_sales.aggregate(total=Sum('total_sale_amount'))['total'] or 0
            uzs_payments = filtered_payments.aggregate(total=Sum('amount'))['total'] or 0
            usd_sales = 0
            usd_payments = 0
            
            # Calculate filtered balance for UZS only
            filtered_balance_uzs = uzs_sales - uzs_payments + (agent.initial_balance_uzs or 0)
            filtered_balance_usd = 0
            
        elif filter_type == 'usd':
            filtered_sales = agent.agent_sales.select_related('related_acquisition__ticket').filter(sale_currency='USD')
            filtered_payments = agent.payments.select_related('paid_to_account').filter(currency='USD')
            
            usd_sales = filtered_sales.aggregate(total=Sum('total_sale_amount'))['total'] or 0
            usd_payments = filtered_payments.aggregate(total=Sum('amount'))['total'] or 0
            uzs_sales = 0
            uzs_payments = 0
            
            # Calculate filtered balance for USD only
            filtered_balance_uzs = 0
            filtered_balance_usd = usd_sales - usd_payments + (agent.initial_balance_usd or 0)
            
        elif filter_type == 'umra':
            filtered_sales = agent.agent_sales.select_related('related_acquisition__ticket').filter(related_acquisition__ticket__ticket_type='UMRA')
            filtered_payments = agent.payments.select_related('paid_to_account').none()  # No payments are specific to ticket type
            
            uzs_sales = filtered_sales.filter(sale_currency='UZS').aggregate(total=Sum('total_sale_amount'))['total'] or 0
            usd_sales = filtered_sales.filter(sale_currency='USD').aggregate(total=Sum('total_sale_amount'))['total'] or 0
            uzs_payments = 0
            usd_payments = 0
            
            # Calculate filtered balance for UMRA only (no initial balance included for ticket-type filters)
            filtered_balance_uzs = uzs_sales - uzs_payments
            filtered_balance_usd = usd_sales - usd_payments
            
        else:  # filter_type == 'all'
            filtered_sales = agent.agent_sales.select_related('related_acquisition__ticket')
            filtered_payments = agent.payments.select_related('paid_to_account')
            
            uzs_sales = filtered_sales.filter(sale_currency='UZS').aggregate(total=Sum('total_sale_amount'))['total'] or 0
            usd_sales = filtered_sales.filter(sale_currency='USD').aggregate(total=Sum('total_sale_amount'))['total'] or 0
            uzs_payments = filtered_payments.filter(currency='UZS').aggregate(total=Sum('amount'))['total'] or 0
            usd_payments = filtered_payments.filter(currency='USD').aggregate(total=Sum('amount'))['total'] or 0
            
            # Use actual agent balance for 'all' filter
            filtered_balance_uzs = agent.balance_uzs
            filtered_balance_usd = agent.balance_usd
        
        context.update({
            'transactions': paginated_transactions,
            'sales': sales,
            'payments': payments,
            'payment_form': AgentPaymentForm(),
            'current_filter': filter_type,
            'uzs_sales': uzs_sales,
            'usd_sales': usd_sales,
            'uzs_payments': uzs_payments,
            'usd_payments': usd_payments,
            'filtered_balance_uzs': filtered_balance_uzs,
            'filtered_balance_usd': filtered_balance_usd,
        })
        return context


def add_payment(request, contact_pk, contact_type):
    """Unified payment handler for both agents and suppliers"""
    if contact_type == 'agent':
        contact = get_object_or_404(Agent, pk=contact_pk)
        form_class = AgentPaymentForm
        redirect_name = 'contacts:agent-detail'
    else:  # supplier
        contact = get_object_or_404(Supplier, pk=contact_pk)
        form_class = SupplierPaymentForm
        redirect_name = 'contacts:supplier-detail'
    
    if request.method == 'POST':
        form = form_class(request.POST)
        if form.is_valid():
            try:
                payment = form.save(commit=False)
                if contact_type == 'agent':
                    payment.agent = contact
                    
                    # Handle cross-currency payment for agents
                    if form.cleaned_data.get('payment_type') == 'cross_currency':
                        payment.original_amount = form.cleaned_data['original_amount']
                        payment.original_currency = form.cleaned_data['original_currency']
                        payment.exchange_rate = form.cleaned_data['exchange_rate']
                        
                        # For cross-currency payments:
                        # - payment.amount = converted amount (for debt reduction)
                        # - payment.currency = debt currency being paid
                        # - but actual money goes to account matching original_currency
                        
                        # Save payment first
                        payment.save()
                        
                        # Reduce debt using converted amount in the target currency
                        contact.reduce_debt(payment.amount, payment.currency)
                        
                        # Add actual money received to account in original currency
                        payment.paid_to_account.current_balance += payment.original_amount
                        payment.paid_to_account.save(update_fields=['current_balance', 'updated_at'])
                    else:
                        # Normal same-currency payment
                        payment.save()
                        contact.reduce_debt(payment.amount, payment.currency)
                        payment.paid_to_account.current_balance += payment.amount
                        payment.paid_to_account.save(update_fields=['current_balance', 'updated_at'])
                else:
                    payment.supplier = contact
                    payment.save()
                    contact.reduce_debt(payment.amount, payment.currency)
                    payment.paid_from_account.current_balance -= payment.amount
                    payment.paid_from_account.save(update_fields=['current_balance', 'updated_at'])
                
                # Success - add success message and redirect
                messages.success(request, f"To'lov muvaffaqiyatli qabul qilindi!")
                return redirect(redirect_name, pk=contact_pk)
                
            except Exception as e:
                logger.error(f"Error creating {contact_type} payment: {e}")
                messages.error(request, f"To'lov qabul qilishda xatolik yuz berdi: {str(e)}")
                return redirect(redirect_name, pk=contact_pk)
        else:
            # Form validation failed - show errors
            error_messages = []
            for field, errors in form.errors.items():
                for error in errors:
                    error_messages.append(f"{field}: {error}")
            messages.error(request, f"Form xatosi: {'; '.join(error_messages)}")
            logger.error(f"Form validation failed for {contact_type} payment: {form.errors}")
            return redirect(redirect_name, pk=contact_pk)

    return redirect(redirect_name, pk=contact_pk)


def add_agent_payment(request, agent_pk):
    return add_payment(request, agent_pk, 'agent')


def add_supplier_payment(request, supplier_pk):
    return add_payment(request, supplier_pk, 'supplier')


@login_required(login_url='/core/login/')
def api_agents_list(request):
    """API endpoint to get list of agents for dropdowns"""
    agents = Agent.objects.filter().values('id', 'name').order_by('name')
    return JsonResponse(list(agents), safe=False)
