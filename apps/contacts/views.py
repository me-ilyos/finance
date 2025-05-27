from django.shortcuts import render, redirect
from django.views import View
from django.contrib import messages
from django.core.paginator import Paginator
from .models import Agent, Supplier
from .forms import AgentForm, SupplierForm

# Create your views here.

class AgentListView(View):
    def get(self, request):
        agents = Agent.objects.all().order_by('-created_at')
        paginator = Paginator(agents, 10) # Show 10 agents per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        agent_form = AgentForm()
        return render(request, 'contacts/agent_list.html', {
            'agents': page_obj,
            'agent_form': agent_form,
            'is_paginated': page_obj.has_other_pages(),
            'page_obj': page_obj
        })

    def post(self, request):
        agent_form = AgentForm(request.POST)
        if agent_form.is_valid():
            agent_form.save()
            messages.success(request, "Agent muvaffaqiyatli qo'shildi.")
            return redirect('contacts:agent-list')
        else:
            messages.error(request, "Agent qo'shishda xatolik yuz berdi.")
            agents = Agent.objects.all().order_by('-created_at')
            paginator = Paginator(agents, 10)
            page_number = request.GET.get('page')
            page_obj = paginator.get_page(page_number)
            return render(request, 'contacts/agent_list.html', {
                'agents': page_obj,
                'agent_form': agent_form,
                'is_paginated': page_obj.has_other_pages(),
                'page_obj': page_obj
            })

class SupplierListView(View):
    def get(self, request):
        suppliers = Supplier.objects.all().order_by('-created_at')
        paginator = Paginator(suppliers, 10)  # Show 10 suppliers per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        supplier_form = SupplierForm()
        return render(request, 'contacts/supplier_list.html', {
            'suppliers': page_obj,
            'supplier_form': supplier_form,
            'is_paginated': page_obj.has_other_pages(),
            'page_obj': page_obj
        })

    def post(self, request):
        supplier_form = SupplierForm(request.POST)
        if supplier_form.is_valid():
            supplier_form.save()
            messages.success(request, "Ta\'minotchi muvaffaqiyatli qo\'shildi.")
            return redirect('contacts:supplier-list')
        else:
            messages.error(request, "Ta\'minotchi qo\'shishda xatolik yuz berdi.")
            suppliers = Supplier.objects.all().order_by('-created_at')
            paginator = Paginator(suppliers, 10)
            page_number = request.GET.get('page')
            page_obj = paginator.get_page(page_number)
            return render(request, 'contacts/supplier_list.html', {
                'suppliers': page_obj,
                'supplier_form': supplier_form,
                'is_paginated': page_obj.has_other_pages(),
                'page_obj': page_obj
            })
