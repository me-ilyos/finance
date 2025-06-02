from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.views.generic import DetailView, UpdateView, ListView, CreateView
from django.urls import reverse_lazy, reverse
from django.http import HttpResponseRedirect
import logging

from .models import Agent, Supplier, AgentPayment
from .forms import AgentForm, SupplierForm, AgentPaymentForm
from .services import ContactFormService, AgentPaymentService

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
            ContactFormService.create_agent(form.cleaned_data)
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
            ContactFormService.create_supplier(form.cleaned_data)
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Use service to get supplier acquisitions
        from django.apps import apps
        from django.db.models import Sum, Count, Q
        
        Acquisition = apps.get_model('inventory', 'Acquisition')
        
        # Get all acquisitions for this supplier
        acquisitions = Acquisition.objects.filter(
            supplier=self.object
        ).select_related('ticket').order_by('-acquisition_date')
        
        context['supplier_acquisitions'] = acquisitions
        
        # Add summary statistics - calculate totals by currency
        total_acquisitions = acquisitions.count()
        total_cost_uzs = acquisitions.filter(
            transaction_currency='UZS'
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        total_cost_usd = acquisitions.filter(
            transaction_currency='USD'
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        context['acquisition_stats'] = {
            'total_acquisitions': total_acquisitions,
            'total_cost_uzs': total_cost_uzs,
            'total_cost_usd': total_cost_usd,
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
        context['agent_sales'] = agent.agent_sales.all().order_by('-sale_date')
        context['agent_payments'] = agent.payments.all().order_by('-payment_date')
        context['payment_form'] = AgentPaymentForm(initial={'agent': agent.pk}, agent=agent)
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
            payment, error = AgentPaymentService.create_payment(form, agent)
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
