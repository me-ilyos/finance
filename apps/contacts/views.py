from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.views.generic import DetailView, UpdateView, ListView, CreateView
from django.urls import reverse_lazy, reverse
from django.http import HttpResponseRedirect
import logging

from .models import Agent, Supplier, AgentPayment
from .forms import AgentForm, SupplierForm, AgentPaymentForm
from .services import create_agent_payment, create_agent, create_supplier

logger = logging.getLogger(__name__)


class AgentListView(CreateView):
    """Combined list and create view for agents"""
    model = Agent
    form_class = AgentForm
    template_name = 'contacts/agent_list.html'
    success_url = reverse_lazy('contacts:agent-list')
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['agents'] = Agent.objects.all().order_by('-created_at')
        context['agent_form'] = context['form']
        return context

    def form_valid(self, form):
        try:
            create_agent(form.cleaned_data)
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
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['suppliers'] = Supplier.objects.all().order_by('-created_at')
        context['supplier_form'] = context['form']
        return context

    def form_valid(self, form):
        try:
            create_supplier(form.cleaned_data)
            messages.success(self.request, "Yetkazib beruvchi muvaffaqiyatli qo'shildi.")
        except Exception as e:
            logger.error(f"Error creating supplier: {e}")
            messages.error(self.request, "Yetkazib beruvchi yaratishda xatolik yuz berdi.")
        return HttpResponseRedirect(self.success_url)

    def form_invalid(self, form):
        messages.error(self.request, "Yetkazib beruvchi qo'shishda xatolik. Ma'lumotlarni tekshiring.")
        return super().form_invalid(form)


class SupplierDetailView(DetailView):
    """Detail view for suppliers"""
    model = Supplier
    template_name = 'contacts/supplier_detail.html'

    def get_queryset(self):
        return Supplier.objects.prefetch_related(
            'acquisitions_from_supplier__ticket',
            'payments_received'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        supplier = self.object
        
        # Get acquisitions using the correct related name
        acquisitions = supplier.acquisitions_from_supplier.select_related('ticket').order_by('-acquisition_date')
        context['supplier_acquisitions'] = acquisitions
        
        # Get supplier payments (expenditures to this supplier)
        from apps.accounting.models import Expenditure
        from apps.accounting.forms import SupplierPaymentForm
        
        payments = supplier.payments_received.filter(
            expenditure_type=Expenditure.ExpenditureType.SUPPLIER_PAYMENT
        ).order_by('-expenditure_date')
        context['supplier_payments'] = payments
        
        # Create combined transactions list for the new table format
        combined_transactions = []
        
        # Add acquisitions to combined list
        for acquisition in acquisitions:
            combined_transactions.append({
                'date': acquisition.acquisition_date,
                'type': 'acquisition',
                'amount': acquisition.total_amount,
                'currency': acquisition.transaction_currency,
                'id': acquisition.id,
                'ticket_description': acquisition.ticket.description if acquisition.ticket else None,
                'notes': acquisition.notes,
            })
        
        # Add payments to combined list
        for payment in payments:
            combined_transactions.append({
                'date': payment.expenditure_date,
                'type': 'payment',
                'amount': payment.amount,
                'currency': payment.currency,
                'id': payment.id,
                'ticket_description': None,
                'notes': payment.notes,
            })
        
        # Sort by date descending (newest first)
        combined_transactions.sort(key=lambda x: x['date'], reverse=True)
        context['combined_transactions'] = combined_transactions
        
        # Calculate totals for summary - only unpaid acquisitions create debt
        unpaid_acquisitions_uzs = sum(a.total_amount for a in acquisitions if a.transaction_currency == 'UZS' and not a.paid_from_account)
        unpaid_acquisitions_usd = sum(a.total_amount for a in acquisitions if a.transaction_currency == 'USD' and not a.paid_from_account)
        
        # Only count manual payments (not automatic expenditures from paid acquisitions) as debt-reducing
        manual_payments_uzs = sum(p.amount for p in payments if p.currency == 'UZS' and not (p.notes and p.notes.startswith('Automatic expenditure')))
        manual_payments_usd = sum(p.amount for p in payments if p.currency == 'USD' and not (p.notes and p.notes.startswith('Automatic expenditure')))
        
        # Total payments includes all payments for display purposes
        total_payments_uzs = sum(p.amount for p in payments if p.currency == 'UZS')
        total_payments_usd = sum(p.amount for p in payments if p.currency == 'USD')
        
        # Use database current balance as the accurate current debt (includes initial balance)
        current_balance_uzs = supplier.current_balance_uzs
        current_balance_usd = supplier.current_balance_usd
        
        # Calculate opening balance: Current Balance - Unpaid Acquisitions + Manual Payments
        # This shows what the initial balance was before transactions
        opening_balance_uzs = current_balance_uzs - unpaid_acquisitions_uzs + manual_payments_uzs
        opening_balance_usd = current_balance_usd - unpaid_acquisitions_usd + manual_payments_usd
        
        context['transaction_summary'] = {
            'opening_balance_uzs': opening_balance_uzs,
            'opening_balance_usd': opening_balance_usd,
            'total_acquisitions_uzs': sum(a.total_amount for a in acquisitions if a.transaction_currency == 'UZS'),
            'total_acquisitions_usd': sum(a.total_amount for a in acquisitions if a.transaction_currency == 'USD'),
            'unpaid_acquisitions_uzs': unpaid_acquisitions_uzs,
            'unpaid_acquisitions_usd': unpaid_acquisitions_usd,
            'total_payments_uzs': total_payments_uzs,
            'total_payments_usd': total_payments_usd,
            'manual_payments_uzs': manual_payments_uzs,
            'manual_payments_usd': manual_payments_usd,
            'current_balance_uzs': current_balance_uzs,
            'current_balance_usd': current_balance_usd,
        }
        
        # Add payment form for the modal
        context['payment_form'] = SupplierPaymentForm(supplier=supplier)
        
        # Get supplier statistics using manager
        context['supplier_stats'] = Supplier.objects.get_supplier_stats(supplier)
        
        # Get debt information
        context['supplier_debt'] = supplier.get_total_debt()
        context['has_debt'] = supplier.has_debt()
        
        # Simple acquisition statistics
        context['acquisition_stats'] = {
            'total_acquisitions': acquisitions.count(),
            'total_cost_uzs': sum(a.total_amount for a in acquisitions if a.transaction_currency == 'UZS'),
            'total_cost_usd': sum(a.total_amount for a in acquisitions if a.transaction_currency == 'USD'),
        }
        
        return context


class AgentDetailView(DetailView):
    """Detail view for agents"""
    model = Agent
    template_name = 'contacts/agent_detail.html'

    def get_queryset(self):
        return Agent.objects.prefetch_related(
            'agent_sales__related_acquisition__ticket',
            'agent_sales__paid_to_account',
            'payments__paid_to_account'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent = self.object
        
        # Use model manager for statistics
        context['agent_stats'] = Agent.objects.get_agent_stats(agent)
        context['agent_sales'] = agent.agent_sales.all().order_by('-sale_date')
        context['agent_payments'] = agent.payments.all().order_by('-payment_date')
        context['payment_form'] = AgentPaymentForm(initial={'agent': agent.pk}, agent=agent)
        
        # Create combined transactions list for the new table format
        combined_transactions = []
        
        # Add sales to combined list
        for sale in context['agent_sales']:
            combined_transactions.append({
                'date': sale.sale_date,
                'type': 'sale',
                'amount': sale.total_sale_amount,
                'currency': sale.sale_currency,
                'id': sale.id,
                'ticket_description': sale.related_acquisition.ticket.description if sale.related_acquisition and sale.related_acquisition.ticket else None,
                'notes': sale.notes,
            })
        
        # Add payments to combined list
        for payment in context['agent_payments']:
            payment_amount = payment.amount_paid_uzs if payment.amount_paid_uzs > 0 else payment.amount_paid_usd
            payment_currency = 'UZS' if payment.amount_paid_uzs > 0 else 'USD'
            combined_transactions.append({
                'date': payment.payment_date,
                'type': 'payment',
                'amount': payment_amount,
                'currency': payment_currency,
                'id': payment.id,
                'ticket_description': None,
                'notes': payment.notes,
            })
        
        # Sort by date descending (newest first)
        combined_transactions.sort(key=lambda x: x['date'], reverse=True)
        context['combined_transactions'] = combined_transactions
        
        # Calculate transaction summary
        total_sales_uzs = sum(s.total_sale_amount for s in context['agent_sales'] if s.sale_currency == 'UZS')
        total_sales_usd = sum(s.total_sale_amount for s in context['agent_sales'] if s.sale_currency == 'USD')
        total_payments_uzs = sum(p.amount_paid_uzs for p in context['agent_payments'])
        total_payments_usd = sum(p.amount_paid_usd for p in context['agent_payments'])
        
        context['transaction_summary'] = {
            'total_sales_uzs': total_sales_uzs,
            'total_sales_usd': total_sales_usd,
            'total_payments_uzs': total_payments_uzs,
            'total_payments_usd': total_payments_usd,
        }
        
        return context


class AgentUpdateView(UpdateView):
    """Update view for agents"""
    model = Agent
    form_class = AgentForm
    template_name = 'contacts/contact_form.html'
    success_url = reverse_lazy('contacts:agent-list')

    def form_valid(self, form):
        messages.success(self.request, "Agent muvaffaqiyatli yangilandi.")
        return super().form_valid(form)


class SupplierUpdateView(UpdateView):
    """Update view for suppliers"""
    model = Supplier
    form_class = SupplierForm
    template_name = 'contacts/contact_form.html'
    success_url = reverse_lazy('contacts:supplier-list')

    def form_valid(self, form):
        messages.success(self.request, "Yetkazib beruvchi muvaffaqiyatli yangilandi.")
        return super().form_valid(form)


def add_agent_payment(request, agent_pk):
    """Simple function-based view for adding agent payments"""
    agent = get_object_or_404(Agent, pk=agent_pk)
    
    if request.method == 'POST':
        form = AgentPaymentForm(request.POST, agent=agent)
        if form.is_valid():
            payment, error = create_agent_payment(form, agent)
            if payment:
                messages.success(request, "Agent to'lovi muvaffaqiyatli qo'shildi.")
            else:
                messages.error(request, error)
        else:
            for field, errors in form.errors.items():
                field_label = form.fields[field].label if field != '__all__' else 'Forma'
                for error in errors:
                    messages.error(request, f"{field_label}: {error}")

    return redirect(reverse('contacts:agent-detail', kwargs={'pk': agent_pk}))


def add_supplier_payment(request, supplier_pk):
    """Simple function-based view for adding supplier payments"""
    from apps.accounting.forms import SupplierPaymentForm
    from django.core.exceptions import ValidationError
    from django.db import transaction
    
    supplier = get_object_or_404(Supplier, pk=supplier_pk)
    
    if request.method == 'POST':
        form = SupplierPaymentForm(request.POST, supplier=supplier)
        if form.is_valid():
            try:
                with transaction.atomic():
                    payment = form.save()
                    messages.success(request, f"Ta'minotchi {supplier.name}ga to'lov muvaffaqiyatli amalga oshirildi.")
                    logger.info(f"Created supplier payment {payment.pk} for supplier {supplier.pk}")
            except ValidationError as e:
                messages.error(request, f"To'lovni saqlashda xatolik: {e}")
                logger.error(f"Validation error creating supplier payment for supplier {supplier.pk}: {e}")
            except Exception as e:
                messages.error(request, f"Kutilmagan xatolik: {e}")
                logger.error(f"Unexpected error creating supplier payment for supplier {supplier.pk}: {e}")
        else:
            for field, errors in form.errors.items():
                field_label = form.fields[field].label if field != '__all__' else 'Forma'
                for error in errors:
                    messages.error(request, f"{field_label}: {error}")

    return redirect(reverse('contacts:supplier-detail', kwargs={'pk': supplier_pk}))
