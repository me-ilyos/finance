from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib import messages
from django.core.paginator import Paginator
from .models import Agent, Supplier, AgentPayment
from .forms import AgentForm, SupplierForm, AgentPaymentForm
from django.views.generic import ListView, CreateView, DetailView, UpdateView
from apps.sales.models import Sale # To list sales related to an agent
from django.urls import reverse_lazy, reverse # Added reverse
from django.db import transaction # Added transaction
from decimal import Decimal # Added Decimal
from django.core.exceptions import ValidationError # Added ValidationError

# Create your views here.

class AgentListView(View):
    def get(self, request):
        agents = Agent.objects.all().order_by('-created_at')
        paginator = Paginator(agents, 10) # Show 10 agents per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        # agent_form = AgentForm() # Removed, add handled by AgentCreateView via button
        return render(request, 'contacts/agent_list.html', {
            'agents': page_obj,
            # 'agent_form': agent_form,
            'is_paginated': page_obj.has_other_pages(),
            'page_obj': page_obj
        })

    # POST method removed from AgentListView, handled by AgentCreateView

class SupplierListView(View):
    def get(self, request):
        suppliers = Supplier.objects.all().order_by('-created_at')
        paginator = Paginator(suppliers, 10)  # Show 10 suppliers per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        # supplier_form = SupplierForm() # Removed, add handled by SupplierCreateView via button
        return render(request, 'contacts/supplier_list.html', {
            'suppliers': page_obj,
            # 'supplier_form': supplier_form,
            'is_paginated': page_obj.has_other_pages(),
            'page_obj': page_obj
        })
    # POST method removed from SupplierListView, handled by SupplierCreateView

class AgentDetailView(DetailView):
    model = Agent
    template_name = 'contacts/agent_detail.html'
    context_object_name = 'agent'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent = self.get_object()
        context['agent_sales'] = Sale.objects.filter(agent=agent).select_related(
            'related_acquisition', 'related_acquisition__ticket', 'paid_to_account'
        ).order_by('-sale_date')
        
        # Add payment form to context
        context['payment_form'] = AgentPaymentForm(initial={'agent': agent.pk}, agent=agent) 
        # Add agent payments to context
        context['agent_payments'] = AgentPayment.objects.filter(agent=agent).select_related('paid_to_account').order_by('-payment_date')
        return context

class AgentCreateView(CreateView):
    model = Agent
    form_class = AgentForm
    template_name = 'contacts/agent_form.html' # Should be a generic form template or specific create form
    success_url = reverse_lazy('contacts:agent-list')

    def form_valid(self, form):
        messages.success(self.request, "Agent muvaffaqiyatli qo'shildi.")
        return super().form_valid(form)

class AgentUpdateView(UpdateView): # Added AgentUpdateView
    model = Agent
    form_class = AgentForm
    template_name = 'contacts/agent_form.html' # Can reuse the same form template
    success_url = reverse_lazy('contacts:agent-list')

    def form_valid(self, form):
        messages.success(self.request, "Agent muvaffaqiyatli yangilandi.")
        return super().form_valid(form)

class SupplierCreateView(CreateView): # Added SupplierCreateView
    model = Supplier
    form_class = SupplierForm
    template_name = 'contacts/supplier_form.html' # Should be a generic form template or specific create form
    success_url = reverse_lazy('contacts:supplier-list')

    def form_valid(self, form):
        messages.success(self.request, "Yetkazib beruvchi muvaffaqiyatli qo'shildi.")
        return super().form_valid(form)

class SupplierUpdateView(UpdateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'contacts/supplier_form.html'
    success_url = reverse_lazy('contacts:supplier-list')

    def form_valid(self, form):
        messages.success(self.request, "Yetkazib beruvchi muvaffaqiyatli yangilandi.")
        return super().form_valid(form)

def add_agent_payment(request, agent_pk):
    agent = get_object_or_404(Agent, pk=agent_pk)
    if request.method == 'POST':
        form = AgentPaymentForm(request.POST, agent=agent)
        if form.is_valid():
            try:
                with transaction.atomic():
                    payment = form.save(commit=False)
                    payment.agent = agent
                    payment.save() # This will call AgentPayment.save() which updates FinancialAccount

                    # Update agent's outstanding balance
                    agent.update_balance_on_payment(
                        amount_paid_uzs=payment.amount_paid_uzs or Decimal('0.00'),
                        amount_paid_usd=payment.amount_paid_usd or Decimal('0.00')
                    )
                messages.success(request, "Agent to'lovi muvaffaqiyatli qo'shildi.")
            except ValidationError as e:
                messages.error(request, f"To'lovni saqlashda xatolik: {e}")
            except Exception as e:
                messages.error(request, f"Kutilmagan xatolik: {e}")
        else:
            # Form is invalid, gather errors to display
            error_message = "To'lovni qo'shishda xatolik. Iltimos, ma'lumotlarni tekshiring."
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label if field != '__all__' else 'Forma'}: {error}")
            # messages.error(request, error_message)

    # Always redirect back to agent detail page, messages will be displayed there
    return redirect(reverse('contacts:agent-detail', kwargs={'pk': agent_pk}))
