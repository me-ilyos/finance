from django.shortcuts import get_object_or_404, redirect
from django.views.generic import DetailView, CreateView
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect, JsonResponse
from django.db.models import Sum, Q, Case, When, Value, IntegerField
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from datetime import datetime, date
import logging
import re

from .models import Agent, Supplier, AgentPayment, SupplierPayment, Commission
from .forms import AgentForm, SupplierForm, AgentPaymentForm, SupplierPaymentForm, CommissionForm

logger = logging.getLogger(__name__)


def enhanced_search_queryset(queryset, search_query, name_field='name'):
    """
    Enhanced search function that provides better matching for names.
    
    This function implements multiple search strategies:
    1. Exact match (highest priority)
    2. Starts with match (high priority)
    3. Contains match (medium priority)
    4. Word boundary matches (for partial names)
    5. Similar word matches (for typos like Son/Sol)
    
    Args:
        queryset: Django queryset to search in
        search_query: Search string from user
        name_field: Field name to search in (default: 'name')
    
    Returns:
        Filtered queryset with results ordered by relevance
    """
    if not search_query.strip():
        return queryset
    
    search_query = search_query.strip()
    search_terms = search_query.split()
    
    # Build Q objects for different search strategies
    q_objects = []
    
    # Strategy 1: Exact match (highest priority)
    exact_q = Q(**{f"{name_field}__iexact": search_query})
    q_objects.append(exact_q)
    
    # Strategy 2: Starts with match (high priority)
    starts_with_q = Q(**{f"{name_field}__istartswith": search_query})
    q_objects.append(starts_with_q)
    
    # Strategy 3: Contains match (medium priority)
    contains_q = Q(**{f"{name_field}__icontains": search_query})
    q_objects.append(contains_q)
    
    # Strategy 4: Word boundary matches (for partial names)
    # This helps with cases like "Sol" matching "Sol Campbell"
    word_boundary_terms = []
    for term in search_terms:
        if len(term) >= 2:  # Only search for terms with 2+ characters
            word_boundary_terms.append(term)
    
    if word_boundary_terms:
        word_q = Q()
        for term in word_boundary_terms:
            # Use regex to match word boundaries
            word_q |= Q(**{f"{name_field}__iregex": rf'\b{re.escape(term)}'})
        q_objects.append(word_q)
    
    # Strategy 5: Similar word matches (for typos and abbreviations)
    # This helps with cases like "Son" matching "Sol Campbell"
    partial_q = Q()
    for term in search_terms:
        if len(term) >= 2:
            partial_q |= Q(**{f"{name_field}__icontains": term})
    q_objects.append(partial_q)
    
    # Combine all strategies with OR
    combined_q = q_objects[0]
    for q_obj in q_objects[1:]:
        combined_q |= q_obj
    
    # Apply the filter
    filtered_queryset = queryset.filter(combined_q)
    
    # Create a relevance annotation for better ordering
    relevance_annotation = Case(
        When(**{f"{name_field}__iexact": search_query}, then=Value(5)),  # Exact match
        When(**{f"{name_field}__istartswith": search_query}, then=Value(4)),  # Starts with
        When(**{f"{name_field}__icontains": search_query}, then=Value(3)),  # Contains match
        default=Value(1),  # Other matches
        output_field=IntegerField(),
    )
    
    # Apply annotation and order by relevance, then by name
    return filtered_queryset.annotate(
        relevance=relevance_annotation
    ).order_by('-relevance', name_field)


class AgentListView(CreateView):
    model = Agent
    form_class = AgentForm
    template_name = 'contacts/agent_list.html'
    success_url = reverse_lazy('contacts:agent-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get search parameter
        search_query = self.request.GET.get('search', '')
        
        # Filter agents using enhanced search
        agents = Agent.objects.all().order_by('-created_at')
        if search_query:
            agents = enhanced_search_queryset(agents, search_query, 'name')
        else:
            agents = agents.order_by('-created_at')
        
        # Pagination
        paginator = Paginator(agents, 20)  # 20 agents per page
        page = self.request.GET.get('page')
        
        try:
            agents_page = paginator.page(page)
        except PageNotAnInteger:
            agents_page = paginator.page(1)
        except EmptyPage:
            agents_page = paginator.page(paginator.num_pages)
        
        context['agents'] = agents_page
        context['is_paginated'] = paginator.num_pages > 1
        context['page_obj'] = agents_page
        context['search_query'] = search_query
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
        
        # Get search parameter
        search_query = self.request.GET.get('search', '')
        
        # Show only active suppliers and filter using enhanced search
        suppliers = Supplier.objects.filter(is_active=True).order_by('-created_at')
        if search_query:
            suppliers = enhanced_search_queryset(suppliers, search_query, 'name')
        else:
            suppliers = suppliers.order_by('-created_at')
        
        # Pagination
        paginator = Paginator(suppliers, 20)  # 20 suppliers per page
        page = self.request.GET.get('page')
        
        try:
            suppliers_page = paginator.page(page)
        except PageNotAnInteger:
            suppliers_page = paginator.page(1)
        except EmptyPage:
            suppliers_page = paginator.page(paginator.num_pages)
        
        context['suppliers'] = suppliers_page
        context['is_paginated'] = paginator.num_pages > 1
        context['page_obj'] = suppliers_page
        context['search_query'] = search_query
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
        
        # Get filter parameters from request
        filter_type = self.request.GET.get('filter', 'all')
        page = self.request.GET.get('page', 1)
        start_date = self.request.GET.get('start_date', '')
        end_date = self.request.GET.get('end_date', '')
        
        # Parse dates
        start_date_obj = None
        end_date_obj = None
        
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            except ValueError:
                start_date = ''
        
        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                end_date = ''
        elif start_date and not end_date:
            # If only start date is provided, set end date to today
            end_date_obj = timezone.now().date()
            end_date = end_date_obj.strftime('%Y-%m-%d')
        
        # Get base querysets
        acquisitions = supplier.acquisitions.select_related('ticket').order_by('-acquisition_date')
        payments = supplier.payments.select_related('paid_from_account').order_by('-payment_date')
        commissions = supplier.commissions.select_related('acquisition__ticket').order_by('-commission_date')
        
        # Get ticket returns for this supplier
        from apps.sales.models import TicketReturn
        ticket_returns = TicketReturn.objects.filter(
            original_sale__related_acquisition__supplier=supplier
        ).select_related(
            'original_sale__related_acquisition__ticket'
        ).order_by('-return_date')
        
        # Apply date filtering
        if start_date_obj:
            acquisitions = acquisitions.filter(acquisition_date__gte=start_date_obj)
            payments = payments.filter(payment_date__gte=start_date_obj)
            commissions = commissions.filter(commission_date__gte=start_date_obj)
            ticket_returns = ticket_returns.filter(return_date__date__gte=start_date_obj)
        
        if end_date_obj:
            acquisitions = acquisitions.filter(acquisition_date__lte=end_date_obj)
            payments = payments.filter(payment_date__lte=end_date_obj)
            commissions = commissions.filter(commission_date__lte=end_date_obj)
            ticket_returns = ticket_returns.filter(return_date__date__lte=end_date_obj)
        
        # Apply filtering based on filter_type
        if filter_type == 'uzs':
            acquisitions = acquisitions.filter(currency='UZS')
            payments = payments.filter(currency='UZS')
            commissions = commissions.filter(currency='UZS')
            ticket_returns = ticket_returns.filter(supplier_fine_currency='UZS')
        elif filter_type == 'usd':
            acquisitions = acquisitions.filter(currency='USD')
            payments = payments.filter(currency='USD')
            commissions = commissions.filter(currency='USD')
            ticket_returns = ticket_returns.filter(supplier_fine_currency='USD')
        elif filter_type == 'umra':
            acquisitions = acquisitions.filter(ticket__ticket_type='UMRA')
            payments = payments.none()  # No payments are specific to ticket type
            commissions = commissions.filter(acquisition__ticket__ticket_type='UMRA')
            ticket_returns = ticket_returns.filter(original_sale__related_acquisition__ticket__ticket_type='UMRA')
        
        # Create transactions list including commissions and returns
        transactions = []
        for acq in acquisitions:
            transactions.append({'date': acq.acquisition_date, 'type': 'acquisition', 'acquisition': acq})
        for payment in payments:
            transactions.append({'date': payment.payment_date, 'type': 'payment', 'payment': payment})
        for commission in commissions:
            transactions.append({'date': commission.commission_date, 'type': 'commission', 'commission': commission})
        for return_instance in ticket_returns:
            transactions.append({'date': return_instance.return_date, 'type': 'return', 'return': return_instance})
        
        # Sort by date (oldest first for balance calculation)
        transactions.sort(key=lambda x: x['date'])
        
        # Calculate running balances
        # For date filtering, we want to show the balance changes within the selected period only
        if start_date_obj:
            # For date period filtering, start with zero and show only changes within the period
            starting_balance_uzs = 0
            starting_balance_usd = 0
            current_balance_uzs = 0
            current_balance_usd = 0
        else:
            starting_balance_uzs = supplier.initial_balance_uzs or 0
            starting_balance_usd = supplier.initial_balance_usd or 0
            current_balance_uzs = supplier.initial_balance_uzs or 0
            current_balance_usd = supplier.initial_balance_usd or 0
        
        for transaction in transactions:
            if transaction['type'] == 'acquisition':
                # Acquisition increases our debt to supplier (positive balance)
                if transaction['acquisition'].currency == 'UZS':
                    current_balance_uzs += transaction['acquisition'].total_amount
                else:
                    current_balance_usd += transaction['acquisition'].total_amount
            elif transaction['type'] == 'payment':
                # Payment decreases our debt to supplier (negative balance)
                if transaction['payment'].currency == 'UZS':
                    current_balance_uzs -= transaction['payment'].amount
                else:
                    current_balance_usd -= transaction['payment'].amount
            elif transaction['type'] == 'commission':
                # Commission decreases our debt to supplier (negative balance)
                if transaction['commission'].currency == 'UZS':
                    current_balance_uzs -= transaction['commission'].amount
                else:
                    current_balance_usd -= transaction['commission'].amount
            elif transaction['type'] == 'return':
                # Return reduces our debt for returned tickets (negative balance)
                # AND adds supplier fine (positive balance)
                return_instance = transaction['return']
                returned_amount = return_instance.returned_acquisition_amount
                supplier_fine_amount = return_instance.total_supplier_fine_amount
                
                if return_instance.original_sale.related_acquisition.currency == 'UZS':
                    current_balance_uzs -= returned_amount
                else:
                    current_balance_usd -= returned_amount
                
                if return_instance.supplier_fine_currency == 'UZS':
                    current_balance_uzs += supplier_fine_amount
                else:
                    current_balance_usd += supplier_fine_amount
            
            # Store the balance after this transaction
            transaction['balance_uzs'] = current_balance_uzs
            transaction['balance_usd'] = current_balance_usd
        
        # Keep transactions sorted by oldest first for display
        # transactions.sort(key=lambda x: x['date'], reverse=True)  # Remove this line
        
        # Paginate transactions
        paginator = Paginator(transactions, 20)  # 20 transactions per page
        try:
            paginated_transactions = paginator.page(page)
        except PageNotAnInteger:
            paginated_transactions = paginator.page(1)
        except EmptyPage:
            paginated_transactions = paginator.page(paginator.num_pages)
        
        # Calculate totals for display in table footer - respect current filter and date range
        if filter_type == 'uzs':
            filtered_acquisitions = supplier.acquisitions.select_related('ticket').filter(currency='UZS')
            filtered_payments = supplier.payments.select_related('paid_from_account').filter(currency='UZS')
            filtered_commissions = supplier.commissions.filter(currency='UZS')
            filtered_returns = ticket_returns.filter(supplier_fine_currency='UZS')
            
            # Apply date filtering to totals
            if start_date_obj:
                filtered_acquisitions = filtered_acquisitions.filter(acquisition_date__gte=start_date_obj)
                filtered_payments = filtered_payments.filter(payment_date__gte=start_date_obj)
                filtered_commissions = filtered_commissions.filter(commission_date__gte=start_date_obj)
                filtered_returns = filtered_returns.filter(return_date__date__gte=start_date_obj)
            if end_date_obj:
                filtered_acquisitions = filtered_acquisitions.filter(acquisition_date__lte=end_date_obj)
                filtered_payments = filtered_payments.filter(payment_date__lte=end_date_obj)
                filtered_commissions = filtered_commissions.filter(commission_date__lte=end_date_obj)
                filtered_returns = filtered_returns.filter(return_date__date__lte=end_date_obj)
            
            uzs_acquisitions = filtered_acquisitions.aggregate(total=Sum('total_amount'))['total'] or 0
            uzs_payments = filtered_payments.aggregate(total=Sum('amount'))['total'] or 0
            uzs_commissions = filtered_commissions.aggregate(total=Sum('amount'))['total'] or 0
            
            # Calculate return amounts
            uzs_returned_amount = 0
            uzs_supplier_fines = 0
            for return_instance in filtered_returns:
                if return_instance.original_sale.related_acquisition.currency == 'UZS':
                    uzs_returned_amount += return_instance.returned_acquisition_amount
                uzs_supplier_fines += return_instance.total_supplier_fine_amount
            
            usd_acquisitions = 0
            usd_payments = 0
            usd_commissions = 0
            usd_returned_amount = 0
            usd_supplier_fines = 0
            
            # Calculate filtered balance for UZS only
            if start_date_obj:
                filtered_balance_uzs = uzs_acquisitions - uzs_commissions - uzs_payments - uzs_returned_amount + uzs_supplier_fines
            else:
                filtered_balance_uzs = uzs_acquisitions - uzs_commissions - uzs_payments - uzs_returned_amount + uzs_supplier_fines + (supplier.initial_balance_uzs or 0)
            filtered_balance_usd = 0
            
        elif filter_type == 'usd':
            filtered_acquisitions = supplier.acquisitions.select_related('ticket').filter(currency='USD')
            filtered_payments = supplier.payments.select_related('paid_from_account').filter(currency='USD')
            filtered_commissions = supplier.commissions.filter(currency='USD')
            filtered_returns = ticket_returns.filter(supplier_fine_currency='USD')
            
            # Apply date filtering to totals
            if start_date_obj:
                filtered_acquisitions = filtered_acquisitions.filter(acquisition_date__gte=start_date_obj)
                filtered_payments = filtered_payments.filter(payment_date__gte=start_date_obj)
                filtered_commissions = filtered_commissions.filter(commission_date__gte=start_date_obj)
                filtered_returns = filtered_returns.filter(return_date__date__gte=start_date_obj)
            if end_date_obj:
                filtered_acquisitions = filtered_acquisitions.filter(acquisition_date__lte=end_date_obj)
                filtered_payments = filtered_payments.filter(payment_date__lte=end_date_obj)
                filtered_commissions = filtered_commissions.filter(commission_date__lte=end_date_obj)
                filtered_returns = filtered_returns.filter(return_date__date__lte=end_date_obj)
            
            usd_acquisitions = filtered_acquisitions.aggregate(total=Sum('total_amount'))['total'] or 0
            usd_payments = filtered_payments.aggregate(total=Sum('amount'))['total'] or 0
            usd_commissions = filtered_commissions.aggregate(total=Sum('amount'))['total'] or 0
            
            # Calculate return amounts
            usd_returned_amount = 0
            usd_supplier_fines = 0
            for return_instance in filtered_returns:
                if return_instance.original_sale.related_acquisition.currency == 'USD':
                    usd_returned_amount += return_instance.returned_acquisition_amount
                usd_supplier_fines += return_instance.total_supplier_fine_amount
            
            uzs_acquisitions = 0
            uzs_payments = 0
            uzs_commissions = 0
            uzs_returned_amount = 0
            uzs_supplier_fines = 0
            
            # Calculate filtered balance for USD only
            filtered_balance_uzs = 0
            if start_date_obj:
                filtered_balance_usd = usd_acquisitions - usd_commissions - usd_payments - usd_returned_amount + usd_supplier_fines
            else:
                filtered_balance_usd = usd_acquisitions - usd_commissions - usd_payments - usd_returned_amount + usd_supplier_fines + (supplier.initial_balance_usd or 0)
            
        elif filter_type == 'umra':
            filtered_acquisitions = supplier.acquisitions.select_related('ticket').filter(ticket__ticket_type='UMRA')
            filtered_payments = supplier.payments.select_related('paid_from_account').none()  # No payments are specific to ticket type
            filtered_commissions = supplier.commissions.filter(acquisition__ticket__ticket_type='UMRA')
            filtered_returns = ticket_returns.filter(original_sale__related_acquisition__ticket__ticket_type='UMRA')
            
            # Apply date filtering to totals
            if start_date_obj:
                filtered_acquisitions = filtered_acquisitions.filter(acquisition_date__gte=start_date_obj)
                filtered_commissions = filtered_commissions.filter(commission_date__gte=start_date_obj)
                filtered_returns = filtered_returns.filter(return_date__date__gte=start_date_obj)
            if end_date_obj:
                filtered_acquisitions = filtered_acquisitions.filter(acquisition_date__lte=end_date_obj)
                filtered_commissions = filtered_commissions.filter(commission_date__lte=end_date_obj)
                filtered_returns = filtered_returns.filter(return_date__date__lte=end_date_obj)
            
            uzs_acquisitions = filtered_acquisitions.filter(currency='UZS').aggregate(total=Sum('total_amount'))['total'] or 0
            usd_acquisitions = filtered_acquisitions.filter(currency='USD').aggregate(total=Sum('total_amount'))['total'] or 0
            uzs_payments = 0
            usd_payments = 0
            uzs_commissions = filtered_commissions.filter(currency='UZS').aggregate(total=Sum('amount'))['total'] or 0
            usd_commissions = filtered_commissions.filter(currency='USD').aggregate(total=Sum('amount'))['total'] or 0
            
            # Calculate return amounts
            uzs_returned_amount = 0
            usd_returned_amount = 0
            uzs_supplier_fines = 0
            usd_supplier_fines = 0
            for return_instance in filtered_returns:
                if return_instance.original_sale.related_acquisition.currency == 'UZS':
                    uzs_returned_amount += return_instance.returned_acquisition_amount
                else:
                    usd_returned_amount += return_instance.returned_acquisition_amount
                
                if return_instance.supplier_fine_currency == 'UZS':
                    uzs_supplier_fines += return_instance.total_supplier_fine_amount
                else:
                    usd_supplier_fines += return_instance.total_supplier_fine_amount
            
            # Calculate filtered balance for UMRA only
            if start_date_obj:
                filtered_balance_uzs = uzs_acquisitions - uzs_commissions - uzs_payments - uzs_returned_amount + uzs_supplier_fines
                filtered_balance_usd = usd_acquisitions - usd_commissions - usd_payments - usd_returned_amount + usd_supplier_fines
            else:
                filtered_balance_uzs = uzs_acquisitions - uzs_commissions - uzs_payments - uzs_returned_amount + uzs_supplier_fines
                filtered_balance_usd = usd_acquisitions - usd_commissions - usd_payments - usd_returned_amount + usd_supplier_fines
            
        else:  # filter_type == 'all'
            filtered_acquisitions = supplier.acquisitions.select_related('ticket')
            filtered_payments = supplier.payments.select_related('paid_from_account')
            filtered_commissions = supplier.commissions
            filtered_returns = ticket_returns
            
            # Apply date filtering to totals
            if start_date_obj:
                filtered_acquisitions = filtered_acquisitions.filter(acquisition_date__gte=start_date_obj)
                filtered_payments = filtered_payments.filter(payment_date__gte=start_date_obj)
                filtered_commissions = filtered_commissions.filter(commission_date__gte=start_date_obj)
                filtered_returns = filtered_returns.filter(return_date__date__gte=start_date_obj)
            if end_date_obj:
                filtered_acquisitions = filtered_acquisitions.filter(acquisition_date__lte=end_date_obj)
                filtered_payments = filtered_payments.filter(payment_date__lte=end_date_obj)
                filtered_commissions = filtered_commissions.filter(commission_date__lte=end_date_obj)
                filtered_returns = filtered_returns.filter(return_date__date__lte=end_date_obj)
            
            uzs_acquisitions = filtered_acquisitions.filter(currency='UZS').aggregate(total=Sum('total_amount'))['total'] or 0
            usd_acquisitions = filtered_acquisitions.filter(currency='USD').aggregate(total=Sum('total_amount'))['total'] or 0
            uzs_payments = filtered_payments.filter(currency='UZS').aggregate(total=Sum('amount'))['total'] or 0
            usd_payments = filtered_payments.filter(currency='USD').aggregate(total=Sum('amount'))['total'] or 0
            uzs_commissions = filtered_commissions.filter(currency='UZS').aggregate(total=Sum('amount'))['total'] or 0
            usd_commissions = filtered_commissions.filter(currency='USD').aggregate(total=Sum('amount'))['total'] or 0
            
            # Calculate return amounts
            uzs_returned_amount = 0
            usd_returned_amount = 0
            uzs_supplier_fines = 0
            usd_supplier_fines = 0
            for return_instance in filtered_returns:
                if return_instance.original_sale.related_acquisition.currency == 'UZS':
                    uzs_returned_amount += return_instance.returned_acquisition_amount
                else:
                    usd_returned_amount += return_instance.returned_acquisition_amount
                
                if return_instance.supplier_fine_currency == 'UZS':
                    uzs_supplier_fines += return_instance.total_supplier_fine_amount
                else:
                    usd_supplier_fines += return_instance.total_supplier_fine_amount
            
            # Calculate total balance including commissions and returns for 'all' filter
            if start_date_obj:
                filtered_balance_uzs = uzs_acquisitions - uzs_commissions - uzs_payments - uzs_returned_amount + uzs_supplier_fines
                filtered_balance_usd = usd_acquisitions - usd_commissions - usd_payments - usd_returned_amount + usd_supplier_fines
            else:
                filtered_balance_uzs = uzs_acquisitions - uzs_commissions - uzs_payments - uzs_returned_amount + uzs_supplier_fines + (supplier.initial_balance_uzs or 0)
                filtered_balance_usd = usd_acquisitions - usd_commissions - usd_payments - usd_returned_amount + usd_supplier_fines + (supplier.initial_balance_usd or 0)
        
        context.update({
            'transactions': paginated_transactions,
            'acquisitions': supplier.acquisitions.select_related('ticket').order_by('-acquisition_date'),
            'payments': supplier.payments.select_related('paid_from_account').order_by('-payment_date'),
            'commissions': supplier.commissions.select_related('acquisition__ticket').order_by('-commission_date'),
            'payment_form': SupplierPaymentForm(),
            'commission_form': CommissionForm(supplier=supplier),
            'current_filter': filter_type,
            'start_date': start_date,
            'end_date': end_date,
            'starting_balance_uzs': starting_balance_uzs,
            'starting_balance_usd': starting_balance_usd,
            # Table footer totals (always show complete totals)
            'uzs_acquisitions': uzs_acquisitions,
            'usd_acquisitions': usd_acquisitions,
            'uzs_payments': uzs_payments,
            'usd_payments': usd_payments,
            'uzs_commissions': uzs_commissions,
            'usd_commissions': usd_commissions,
            'uzs_returned_amount': locals().get('uzs_returned_amount', 0),
            'usd_returned_amount': locals().get('usd_returned_amount', 0),
            'uzs_supplier_fines': locals().get('uzs_supplier_fines', 0),
            'usd_supplier_fines': locals().get('usd_supplier_fines', 0),
            'filtered_balance_uzs': filtered_balance_uzs,
            'filtered_balance_usd': filtered_balance_usd,
            # Check if user can deactivate (only admins)
            'can_deactivate': self.request.user.is_superuser,
        })
        return context


@login_required(login_url='/core/login/')
def create_commission(request, supplier_pk):
    """Create commission for supplier"""
    supplier = get_object_or_404(Supplier, pk=supplier_pk)
    
    if request.method == 'POST':
        form = CommissionForm(request.POST, supplier=supplier)
        if form.is_valid():
            try:
                with transaction.atomic():
                    commission = form.save(commit=False)
                    commission.supplier = supplier
                    # Set currency to match the selected acquisition
                    acquisition = form.cleaned_data['acquisition']
                    commission.currency = acquisition.currency
                    commission.save()
                    
                    # Reduce supplier debt (commission means supplier owes us, reducing what we owe them)
                    supplier.reduce_debt(commission.amount, commission.currency)
                    
                    # Recalculate supplier balance to ensure consistency
                    supplier.recalculate_balance()
                    
                    messages.success(request, f"Komissiya muvaffaqiyatli qo'shildi!")
                    
            except Exception as e:
                logger.error(f"Error creating commission: {e}")
                messages.error(request, "Komissiya qo'shishda xatolik yuz berdi.")
        else:
            # Log form validation errors for debugging
            logger.error(f"Commission form validation failed: {form.errors}")
            messages.error(request, "Komissiya formasi to'ldirishda xatolik bor.")
    
    return redirect('contacts:supplier-detail', pk=supplier_pk)


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
        
        # Get filter parameters from request
        filter_type = self.request.GET.get('filter', 'all')
        page = self.request.GET.get('page', 1)
        start_date = self.request.GET.get('start_date', '')
        end_date = self.request.GET.get('end_date', '')
        
        # Parse dates
        start_date_obj = None
        end_date_obj = None
        
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            except ValueError:
                start_date = ''
        
        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                end_date = ''
        elif start_date and not end_date:
            # If only start date is provided, set end date to today
            end_date_obj = timezone.now().date()
            end_date = end_date_obj.strftime('%Y-%m-%d')
        
        # Get base querysets
        sales = agent.agent_sales.select_related('related_acquisition__ticket').order_by('-sale_date')
        payments = agent.payments.select_related('paid_to_account').order_by('-payment_date')
        
        # Get ticket returns for this agent
        from apps.sales.models import TicketReturn
        ticket_returns = TicketReturn.objects.filter(
            original_sale__agent=agent
        ).select_related(
            'original_sale__related_acquisition__ticket'
        ).order_by('-return_date')
        
        # Apply date filtering
        if start_date_obj:
            sales = sales.filter(sale_date__gte=start_date_obj)
            payments = payments.filter(payment_date__gte=start_date_obj)
            ticket_returns = ticket_returns.filter(return_date__date__gte=start_date_obj)
        
        if end_date_obj:
            sales = sales.filter(sale_date__lte=end_date_obj)
            payments = payments.filter(payment_date__lte=end_date_obj)
            ticket_returns = ticket_returns.filter(return_date__date__lte=end_date_obj)
        
        # Apply filtering based on filter_type
        if filter_type == 'uzs':
            sales = sales.filter(sale_currency='UZS')
            payments = payments.filter(currency='UZS')
            ticket_returns = ticket_returns.filter(fine_currency='UZS')
        elif filter_type == 'usd':
            sales = sales.filter(sale_currency='USD')
            payments = payments.filter(currency='USD')
            ticket_returns = ticket_returns.filter(fine_currency='USD')
        elif filter_type == 'umra':
            sales = sales.filter(related_acquisition__ticket__ticket_type='UMRA')
            payments = payments.none()  # No payments are specific to ticket type
            ticket_returns = ticket_returns.filter(original_sale__related_acquisition__ticket__ticket_type='UMRA')
        
        # Create transactions list
        transactions = []
        for sale in sales:
            transactions.append({'date': sale.sale_date, 'type': 'sale', 'sale': sale})
        for payment in payments:
            transactions.append({'date': payment.payment_date, 'type': 'payment', 'payment': payment})
        for return_instance in ticket_returns:
            transactions.append({'date': return_instance.return_date, 'type': 'return', 'return': return_instance})
        
        # Sort by date (oldest first for balance calculation)
        transactions.sort(key=lambda x: x['date'])
        
        # Calculate running balances
        # For date filtering, we want to show the balance changes within the selected period only
        if start_date_obj:
            # For date period filtering, start with zero and show only changes within the period
            starting_balance_uzs = 0
            starting_balance_usd = 0
            current_balance_uzs = 0
            current_balance_usd = 0
        else:
            starting_balance_uzs = agent.initial_balance_uzs or 0
            starting_balance_usd = agent.initial_balance_usd or 0
            current_balance_uzs = agent.initial_balance_uzs or 0
            current_balance_usd = agent.initial_balance_usd or 0
        
        for transaction in transactions:
            if transaction['type'] == 'sale':
                # Sale increases our receivable from agent (positive balance)
                if transaction['sale'].sale_currency == 'UZS':
                    current_balance_uzs += transaction['sale'].total_sale_amount
                else:
                    current_balance_usd += transaction['sale'].total_sale_amount
            elif transaction['type'] == 'payment':
                # Payment decreases our receivable from agent (negative balance)
                if transaction['payment'].currency == 'UZS':
                    current_balance_uzs -= transaction['payment'].amount
                else:
                    current_balance_usd -= transaction['payment'].amount
            elif transaction['type'] == 'return':
                # Return reduces agent debt by original purchase price but adds fine
                return_instance = transaction['return']
                returned_amount = return_instance.returned_acquisition_amount  # Original purchase price
                fine_amount = return_instance.total_fine_amount
                
                if return_instance.original_sale.related_acquisition.currency == 'UZS':
                    current_balance_uzs -= returned_amount
                else:
                    current_balance_usd -= returned_amount
                
                if return_instance.fine_currency == 'UZS':
                    current_balance_uzs += fine_amount
                else:
                    current_balance_usd += fine_amount
            
            # Store the balance after this transaction
            transaction['balance_uzs'] = current_balance_uzs
            transaction['balance_usd'] = current_balance_usd
        
        # Keep transactions sorted by oldest first for display
        # transactions.sort(key=lambda x: x['date'], reverse=True)  # Remove this line
        
        # Paginate transactions
        paginator = Paginator(transactions, 20)  # 20 transactions per page
        try:
            paginated_transactions = paginator.page(page)
        except PageNotAnInteger:
            paginated_transactions = paginator.page(1)
        except EmptyPage:
            paginated_transactions = paginator.page(paginator.num_pages)
        
        # Calculate totals for display in table footer - respect current filter and date range
        if filter_type == 'uzs':
            filtered_sales = agent.agent_sales.filter(sale_currency='UZS')
            filtered_payments = agent.payments.filter(currency='UZS')
            filtered_returns = TicketReturn.objects.filter(
                original_sale__agent=agent,
                fine_currency='UZS'
            )
            
            # Apply date filtering to totals
            if start_date_obj:
                filtered_sales = filtered_sales.filter(sale_date__gte=start_date_obj)
                filtered_payments = filtered_payments.filter(payment_date__gte=start_date_obj)
                filtered_returns = filtered_returns.filter(return_date__date__gte=start_date_obj)
            if end_date_obj:
                filtered_sales = filtered_sales.filter(sale_date__lte=end_date_obj)
                filtered_payments = filtered_payments.filter(payment_date__lte=end_date_obj)
                filtered_returns = filtered_returns.filter(return_date__date__lte=end_date_obj)
            
            uzs_sales = filtered_sales.aggregate(
                total=Sum('total_sale_amount')
            )['total'] or 0
            uzs_payments = filtered_payments.aggregate(total=Sum('amount'))['total'] or 0
            
            # Calculate return amounts
            uzs_returned_amount = 0
            uzs_agent_fines = 0
            for return_instance in filtered_returns:
                if return_instance.original_sale.related_acquisition.currency == 'UZS':
                    uzs_returned_amount += return_instance.returned_acquisition_amount  # Original purchase price
                uzs_agent_fines += return_instance.total_fine_amount
            
            usd_sales = 0
            usd_payments = 0
            
            # Calculate filtered balance for UZS only
            if start_date_obj:
                filtered_balance_uzs = uzs_sales - uzs_payments - uzs_returned_amount + uzs_agent_fines
            else:
                filtered_balance_uzs = uzs_sales - uzs_payments - uzs_returned_amount + uzs_agent_fines + (agent.initial_balance_uzs or 0)
            filtered_balance_usd = 0
            
        elif filter_type == 'usd':
            filtered_sales = agent.agent_sales.filter(sale_currency='USD')
            filtered_payments = agent.payments.filter(currency='USD')
            filtered_returns = TicketReturn.objects.filter(
                original_sale__agent=agent,
                fine_currency='USD'
            )
            
            # Apply date filtering to totals
            if start_date_obj:
                filtered_sales = filtered_sales.filter(sale_date__gte=start_date_obj)
                filtered_payments = filtered_payments.filter(payment_date__gte=start_date_obj)
                filtered_returns = filtered_returns.filter(return_date__date__gte=start_date_obj)
            if end_date_obj:
                filtered_sales = filtered_sales.filter(sale_date__lte=end_date_obj)
                filtered_payments = filtered_payments.filter(payment_date__lte=end_date_obj)
                filtered_returns = filtered_returns.filter(return_date__date__lte=end_date_obj)
            
            usd_sales = filtered_sales.aggregate(
                total=Sum('total_sale_amount')
            )['total'] or 0
            usd_payments = filtered_payments.aggregate(total=Sum('amount'))['total'] or 0
            
            # Calculate return amounts
            usd_returned_amount = 0
            usd_agent_fines = 0
            for return_instance in filtered_returns:
                if return_instance.original_sale.related_acquisition.currency == 'USD':
                    usd_returned_amount += return_instance.returned_acquisition_amount  # Original purchase price
                usd_agent_fines += return_instance.total_fine_amount
            
            uzs_sales = 0
            uzs_payments = 0
            
            # Calculate filtered balance for USD only
            filtered_balance_uzs = 0
            if start_date_obj:
                filtered_balance_usd = usd_sales - usd_payments - usd_returned_amount + usd_agent_fines
            else:
                filtered_balance_usd = usd_sales - usd_payments - usd_returned_amount + usd_agent_fines + (agent.initial_balance_usd or 0)
            
        elif filter_type == 'umra':
            filtered_sales = agent.agent_sales.filter(related_acquisition__ticket__ticket_type='UMRA')
            filtered_payments = agent.payments.none()  # No payments are specific to ticket type
            
            # Apply date filtering to totals
            if start_date_obj:
                filtered_sales = filtered_sales.filter(sale_date__gte=start_date_obj)
            if end_date_obj:
                filtered_sales = filtered_sales.filter(sale_date__lte=end_date_obj)
            
            uzs_sales = filtered_sales.filter(sale_currency='UZS').aggregate(
                total=Sum('total_sale_amount')
            )['total'] or 0
            usd_sales = filtered_sales.filter(sale_currency='USD').aggregate(
                total=Sum('total_sale_amount')
            )['total'] or 0
            uzs_payments = 0
            usd_payments = 0
            
            # Calculate filtered balance for UMRA only
            if start_date_obj:
                filtered_balance_uzs = uzs_sales - uzs_payments
                filtered_balance_usd = usd_sales - usd_payments
            else:
                filtered_balance_uzs = uzs_sales - uzs_payments
                filtered_balance_usd = usd_sales - usd_payments
            
        else:  # filter_type == 'all'
            filtered_sales = agent.agent_sales
            filtered_payments = agent.payments
            
            # Apply date filtering to totals
            if start_date_obj:
                filtered_sales = filtered_sales.filter(sale_date__gte=start_date_obj)
                filtered_payments = filtered_payments.filter(payment_date__gte=start_date_obj)
            if end_date_obj:
                filtered_sales = filtered_sales.filter(sale_date__lte=end_date_obj)
                filtered_payments = filtered_payments.filter(payment_date__lte=end_date_obj)
            
            uzs_sales = filtered_sales.filter(sale_currency='UZS').aggregate(
                total=Sum('total_sale_amount')
            )['total'] or 0
            usd_sales = filtered_sales.filter(sale_currency='USD').aggregate(
                total=Sum('total_sale_amount')
            )['total'] or 0
            uzs_payments = filtered_payments.filter(currency='UZS').aggregate(total=Sum('amount'))['total'] or 0
            usd_payments = filtered_payments.filter(currency='USD').aggregate(total=Sum('amount'))['total'] or 0
            
            # Use actual agent balance for 'all' filter
            if start_date_obj:
                filtered_balance_uzs = uzs_sales - uzs_payments
                filtered_balance_usd = usd_sales - usd_payments
            else:
                filtered_balance_uzs = agent.balance_uzs
                filtered_balance_usd = agent.balance_usd
        
        context.update({
            'transactions': paginated_transactions,
            'sales': agent.agent_sales.select_related('related_acquisition__ticket').order_by('-sale_date'),
            'payments': agent.payments.select_related('paid_to_account').order_by('-payment_date'),
            'payment_form': AgentPaymentForm(),
            'current_filter': filter_type,
            'start_date': start_date,
            'end_date': end_date,
            'starting_balance_uzs': starting_balance_uzs,
            'starting_balance_usd': starting_balance_usd,
            # Table footer totals (always show complete totals)
            'uzs_sales': uzs_sales,
            'usd_sales': usd_sales,
            'uzs_payments': uzs_payments,
            'usd_payments': usd_payments,
            'uzs_returned_amount': locals().get('uzs_returned_amount', 0),
            'usd_returned_amount': locals().get('usd_returned_amount', 0),
            'uzs_agent_fines': locals().get('uzs_agent_fines', 0),
            'usd_agent_fines': locals().get('usd_agent_fines', 0),
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
                logger.error(f"Error processing payment for {contact_type}: {e}")
                messages.error(request, "To'lovni qayta ishlashda xatolik yuz berdi.")
                return redirect(redirect_name, pk=contact_pk)
        else:
            # Form validation errors
            messages.error(request, "To'lov ma'lumotlarida xatolik bor.")
            return redirect(redirect_name, pk=contact_pk)
    
    return redirect(redirect_name, pk=contact_pk)


def add_agent_payment(request, agent_pk):
    return add_payment(request, agent_pk, 'agent')


def add_supplier_payment(request, supplier_pk):
    return add_payment(request, supplier_pk, 'supplier')


@login_required(login_url='/core/login/')
def api_agents_list(request):
    """API endpoint to get list of agents for dropdowns"""
    agents = Agent.objects.values('id', 'name').order_by('name')
    return JsonResponse(list(agents), safe=False)
