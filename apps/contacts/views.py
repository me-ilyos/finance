from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.views.generic import DetailView, CreateView
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
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
            messages.success(self.request, "Agent muvaffaqiyatli qo'shildi.")
        except Exception as e:
            logger.error(f"Error creating Agent: {e}")
            messages.error(self.request, "Agent yaratishda xatolik yuz berdi.")
        return HttpResponseRedirect(self.success_url)

    def form_invalid(self, form):
        messages.error(self.request, "Agent qo'shishda xatolik. Ma'lumotlarni tekshiring.")
        return super().form_invalid(form)


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
            messages.success(self.request, "Ta'minotchi muvaffaqiyatli qo'shildi.")
        except Exception as e:
            logger.error(f"Error creating Supplier: {e}")
            messages.error(self.request, "Ta'minotchi yaratishda xatolik yuz berdi.")
        return HttpResponseRedirect(self.success_url)

    def form_invalid(self, form):
        messages.error(self.request, "Ta'minotchi qo'shishda xatolik. Ma'lumotlarni tekshiring.")
        return super().form_invalid(form)


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
        
        context.update({
            'transactions': transactions,
            'acquisitions': acquisitions,
            'payments': payments,
            'payment_form': SupplierPaymentForm()
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
        
        context.update({
            'transactions': transactions,
            'sales': sales,
            'payments': payments,
            'payment_form': AgentPaymentForm()
        })
        return context


def add_payment(request, contact_pk, contact_type):
    """Unified payment handler for both agents and suppliers"""
    if contact_type == 'agent':
        contact = get_object_or_404(Agent, pk=contact_pk)
        form_class = AgentPaymentForm
        redirect_name = 'contacts:agent-detail'
        success_message = "Agent to'lovi muvaffaqiyatli qo'shildi."
    else:  # supplier
        contact = get_object_or_404(Supplier, pk=contact_pk)
        form_class = SupplierPaymentForm
        redirect_name = 'contacts:supplier-detail'
        success_message = f"Ta'minotchi {contact.name}ga to'lov muvaffaqiyatli amalga oshirildi."
    
    if request.method == 'POST':
        form = form_class(request.POST)
        if form.is_valid():
            try:
                payment = form.save(commit=False)
                if contact_type == 'agent':
                    payment.agent = contact
                    # Handle agent payment business logic
                    payment.save()
                    contact.reduce_debt(payment.amount, payment.currency)
                    payment.paid_to_account.current_balance += payment.amount
                    payment.paid_to_account.save(update_fields=['current_balance', 'updated_at'])
                else:
                    payment.supplier = contact
                    # Handle supplier payment business logic
                    payment.save()
                    contact.reduce_debt(payment.amount, payment.currency)
                    payment.paid_from_account.current_balance -= payment.amount
                    payment.paid_from_account.save(update_fields=['current_balance', 'updated_at'])
                
                messages.success(request, success_message)
            except Exception as e:
                logger.error(f"Error creating {contact_type} payment: {e}")
                messages.error(request, "To'lovni qo'shishda xatolik yuz berdi.")
        else:
            messages.error(request, "To'lov ma'lumotlarini tekshiring.")

    return redirect(redirect_name, pk=contact_pk)


def add_agent_payment(request, agent_pk):
    return add_payment(request, agent_pk, 'agent')


def add_supplier_payment(request, supplier_pk):
    return add_payment(request, supplier_pk, 'supplier')
