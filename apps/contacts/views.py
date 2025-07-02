from django.shortcuts import get_object_or_404, redirect
from django.views.generic import DetailView, CreateView
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from django.db.models import Sum, Q
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


class SupplierListView(CreateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'contacts/supplier_list.html'
    success_url = reverse_lazy('contacts:supplier-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['suppliers'] = Supplier.objects.all().order_by('-created_at')
        return context

    def form_valid(self, form):
        try:
            form.save()
        except Exception as e:
            logger.error(f"Error creating Supplier: {e}")
        return HttpResponseRedirect(self.success_url)


class SupplierDetailView(DetailView):
    model = Supplier
    template_name = 'contacts/supplier_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        supplier = self.object
        
        acquisitions = supplier.acquisitions.select_related('ticket').order_by('-acquisition_date')
        payments = supplier.payments.select_related('paid_from_account').order_by('-payment_date')
        
        transactions = []
        for acq in acquisitions:
            transactions.append({'date': acq.acquisition_date, 'type': 'acquisition', 'acquisition': acq})
        for payment in payments:
            transactions.append({'date': payment.payment_date, 'type': 'payment', 'payment': payment})
        
        transactions.sort(key=lambda x: x['date'], reverse=True)
        
        # Calculate totals for display in table footer
        uzs_acquisitions = acquisitions.filter(currency='UZS').aggregate(
            total=Sum('total_amount'))['total'] or 0
        usd_acquisitions = acquisitions.filter(currency='USD').aggregate(
            total=Sum('total_amount'))['total'] or 0
        
        uzs_payments = payments.filter(currency='UZS').aggregate(
            total=Sum('amount'))['total'] or 0
        usd_payments = payments.filter(currency='USD').aggregate(
            total=Sum('amount'))['total'] or 0
        
        context.update({
            'transactions': transactions,
            'acquisitions': acquisitions,
            'payments': payments,
            'payment_form': SupplierPaymentForm(),
            # Table footer totals
            'uzs_acquisitions': uzs_acquisitions,
            'usd_acquisitions': usd_acquisitions,
            'uzs_payments': uzs_payments,
            'usd_payments': usd_payments,
        })
        return context


class AgentDetailView(DetailView):
    model = Agent
    template_name = 'contacts/agent_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent = self.object
        
        sales = agent.agent_sales.select_related('related_acquisition__ticket').order_by('-sale_date')
        payments = agent.payments.select_related('paid_to_account').order_by('-payment_date')
        
        transactions = []
        for sale in sales:
            transactions.append({'date': sale.sale_date, 'type': 'sale', 'sale': sale})
        for payment in payments:
            transactions.append({'date': payment.payment_date, 'type': 'payment', 'payment': payment})
        
        transactions.sort(key=lambda x: x['date'], reverse=True)
        
        # Calculate totals for display in table footer
        uzs_sales = sales.filter(sale_currency='UZS').aggregate(
            total=Sum('total_sale_amount'))['total'] or 0
        usd_sales = sales.filter(sale_currency='USD').aggregate(
            total=Sum('total_sale_amount'))['total'] or 0
        
        uzs_payments = payments.filter(currency='UZS').aggregate(
            total=Sum('amount'))['total'] or 0
        usd_payments = payments.filter(currency='USD').aggregate(
            total=Sum('amount'))['total'] or 0
        
        context.update({
            'transactions': transactions,
            'sales': sales,
            'payments': payments,
            'payment_form': AgentPaymentForm(),
            # Table footer totals
            'uzs_sales': uzs_sales,
            'usd_sales': usd_sales,
            'uzs_payments': uzs_payments,
            'usd_payments': usd_payments,
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
                
            except Exception as e:
                logger.error(f"Error creating {contact_type} payment: {e}")

    return redirect(redirect_name, pk=contact_pk)


def add_agent_payment(request, agent_pk):
    return add_payment(request, agent_pk, 'agent')


def add_supplier_payment(request, supplier_pk):
    return add_payment(request, supplier_pk, 'supplier')
