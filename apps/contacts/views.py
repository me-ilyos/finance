from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.views.generic import DetailView, ListView, CreateView
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
import logging

from .models import Agent, Supplier, AgentPayment, SupplierPayment
from .forms import AgentForm, SupplierForm, AgentPaymentForm, SupplierPaymentForm

logger = logging.getLogger(__name__)


class BaseContactListView(CreateView):
    template_name = None
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context[self.get_context_object_name()] = self.model.objects.all().order_by('-created_at')
        return context

    def form_valid(self, form):
        try:
            form.save()
            messages.success(self.request, f"{self.get_success_message()} muvaffaqiyatli qo'shildi.")
        except Exception as e:
            logger.error(f"Error creating {self.model.__name__}: {e}")
            messages.error(self.request, f"{self.get_success_message()} yaratishda xatolik yuz berdi.")
        return HttpResponseRedirect(self.success_url)

    def form_invalid(self, form):
        messages.error(self.request, f"{self.get_success_message()} qo'shishda xatolik. Ma'lumotlarni tekshiring.")
        return super().form_invalid(form)

    def get_context_object_name(self):
        raise NotImplementedError
    
    def get_success_message(self):
        raise NotImplementedError


class AgentListView(BaseContactListView):
    model = Agent
    form_class = AgentForm
    template_name = 'contacts/agent_list.html'
    success_url = reverse_lazy('contacts:agent-list')

    def get_context_object_name(self):
        return 'agents'
    
    def get_success_message(self):
        return 'Agent'


class SupplierListView(BaseContactListView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'contacts/supplier_list.html'
    success_url = reverse_lazy('contacts:supplier-list')

    def get_context_object_name(self):
        return 'suppliers'
    
    def get_success_message(self):
        return "Ta'minotchi"


class BaseContactDetailView(DetailView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contact = self.object
        
        transactions_data = self.get_transactions_data(contact)
        context.update(transactions_data)
        
        context['payment_form'] = self.get_payment_form_class()()
        return context
    
    def get_transactions_data(self, contact):
        raise NotImplementedError
    
    def get_payment_form_class(self):
        raise NotImplementedError


class SupplierDetailView(BaseContactDetailView):
    model = Supplier
    template_name = 'contacts/supplier_detail.html'

    def get_transactions_data(self, supplier):
        acquisitions = supplier.acquisitions.select_related('ticket').order_by('-acquisition_date')
        payments = supplier.payments.select_related('paid_from_account').order_by('-payment_date')
        
        transactions = []
        for acq in acquisitions:
            transactions.append({'date': acq.acquisition_date, 'type': 'acquisition', 'acquisition': acq})
        for payment in payments:
            transactions.append({'date': payment.payment_date, 'type': 'payment', 'payment': payment})
        
        transactions.sort(key=lambda x: x['date'], reverse=True)
        
        return {'transactions': transactions, 'acquisitions': acquisitions, 'payments': payments}

    def get_payment_form_class(self):
        return SupplierPaymentForm


class AgentDetailView(BaseContactDetailView):
    model = Agent
    template_name = 'contacts/agent_detail.html'

    def get_transactions_data(self, agent):
        sales = agent.agent_sales.select_related('related_acquisition__ticket').order_by('-sale_date')
        payments = agent.payments.select_related('paid_to_account').order_by('-payment_date')
        
        transactions = []
        for sale in sales:
            transactions.append({'date': sale.sale_date, 'type': 'sale', 'sale': sale})
        for payment in payments:
            transactions.append({'date': payment.payment_date, 'type': 'payment', 'payment': payment})
        
        transactions.sort(key=lambda x: x['date'], reverse=True)
        
        return {'transactions': transactions, 'sales': sales, 'payments': payments}

    def get_payment_form_class(self):
        return AgentPaymentForm


def add_agent_payment(request, agent_pk):
    agent = get_object_or_404(Agent, pk=agent_pk)
    
    if request.method == 'POST':
        form = AgentPaymentForm(request.POST)
        if form.is_valid():
            try:
                payment = form.save(commit=False)
                payment.agent = agent
                payment.save()
                messages.success(request, "Agent to'lovi muvaffaqiyatli qo'shildi.")
            except Exception as e:
                logger.error(f"Error creating agent payment: {e}")
                messages.error(request, "To'lovni qo'shishda xatolik yuz berdi.")
        else:
            messages.error(request, "To'lov ma'lumotlarini tekshiring.")

    return redirect('contacts:agent-detail', pk=agent_pk)


def add_supplier_payment(request, supplier_pk):
    supplier = get_object_or_404(Supplier, pk=supplier_pk)
    
    if request.method == 'POST':
        form = SupplierPaymentForm(request.POST)
        if form.is_valid():
            try:
                payment = form.save(commit=False)
                payment.supplier = supplier
                payment.save()
                messages.success(request, f"Ta'minotchi {supplier.name}ga to'lov muvaffaqiyatli amalga oshirildi.")
            except Exception as e:
                logger.error(f"Error creating supplier payment: {e}")
                messages.error(request, "To'lovni qo'shishda xatolik yuz berdi.")
        else:
            messages.error(request, "To'lov ma'lumotlarini tekshiring.")

    return redirect('contacts:supplier-detail', pk=supplier_pk)
