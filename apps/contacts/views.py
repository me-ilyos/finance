from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.views.generic import DetailView, ListView, CreateView
from django.urls import reverse_lazy, reverse
from django.http import HttpResponseRedirect
import logging

from .models import Agent, Supplier, AgentPayment, SupplierPayment
from .forms import AgentForm, SupplierForm, AgentPaymentForm, SupplierPaymentForm
from apps.accounting.models import Expenditure


logger = logging.getLogger(__name__)


class AgentListView(CreateView):
    """Combined list and create view for agents"""
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
            logger.error(f"Error creating agent: {e}")
            messages.error(self.request, "Agent yaratishda xatolik yuz berdi.")
        return HttpResponseRedirect(self.success_url)

    def form_invalid(self, form):
        messages.error(self.request, "Agent qo'shishda xatolik. Ma'lumotlarni tekshiring.")
        return super().form_invalid(form)


class SupplierListView(CreateView):
    """Combined list and create view for suppliers"""
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
            logger.error(f"Error creating supplier: {e}")
            messages.error(self.request, "Ta'minotchi yaratishda xatolik yuz berdi.")
        return HttpResponseRedirect(self.success_url)

    def form_invalid(self, form):
        messages.error(self.request, "Ta'minotchi qo'shishda xatolik. Ma'lumotlarni tekshiring.")
        return super().form_invalid(form)


class SupplierDetailView(DetailView):
    """Detail view for suppliers"""
    model = Supplier
    template_name = 'contacts/supplier_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        supplier = self.object
        
        acquisitions = supplier.acquisitions.select_related('ticket').order_by('-acquisition_date')
        payments = supplier.payments.select_related('paid_from_account').order_by('-payment_date')
        
        # Combine and sort all transactions by date
        transactions = []
        
        # Add acquisitions
        for acq in acquisitions:
            transactions.append({
                'date': acq.acquisition_date,
                'type': 'acquisition',
                'acquisition': acq,
            })
        
        # Add payments
        for payment in payments:
            transactions.append({
                'date': payment.payment_date,
                'type': 'payment',
                'payment': payment,
            })
        
        # Sort all transactions by date (newest first)
        transactions.sort(key=lambda x: x['date'], reverse=True)
        
        context['transactions'] = transactions
        context['acquisitions'] = acquisitions
        context['payments'] = payments
        context['payment_form'] = SupplierPaymentForm()
        
        # Calculate UZS and USD totals
        context['uzs_acquisitions'] = sum(acq.total_amount for acq in acquisitions if acq.currency == 'UZS')
        context['usd_acquisitions'] = sum(acq.total_amount for acq in acquisitions if acq.currency == 'USD')
        context['uzs_payments'] = sum(payment.amount for payment in payments if payment.currency == 'UZS')
        context['usd_payments'] = sum(payment.amount for payment in payments if payment.currency == 'USD')
        
        # Calculate differences (acquisitions - payments)
        context['uzs_difference'] = context['uzs_acquisitions'] - context['uzs_payments']
        context['usd_difference'] = context['usd_acquisitions'] - context['usd_payments']
        
        # Calculate current balances: Initial Balance + Acquisitions - Payments
        context['uzs_current_balance'] = (supplier.initial_balance_uzs or 0) + context['uzs_acquisitions'] - context['uzs_payments']
        context['usd_current_balance'] = (supplier.initial_balance_usd or 0) + context['usd_acquisitions'] - context['usd_payments']
        
        # Also provide the running balance from the model for comparison
        context['uzs_running_balance'] = supplier.balance_uzs
        context['usd_running_balance'] = supplier.balance_usd
        
        return context


class AgentDetailView(DetailView):
    """Detail view for agents"""
    model = Agent
    template_name = 'contacts/agent_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent = self.object
        
        context['agent_sales'] = agent.agent_sales.select_related('related_acquisition__ticket').order_by('-sale_date')
        context['agent_payments'] = agent.payments.order_by('-payment_date')
        context['payment_form'] = AgentPaymentForm()
        
        return context


def add_agent_payment(request, agent_pk):
    """Simple function-based view for adding agent payments"""
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
    """Simple function-based view for adding supplier payments"""
    
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
