from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
from decimal import Decimal


class DateFilterService:
    """Service class to handle date filtering logic across the application"""
    
    @staticmethod
    def get_date_range(filter_period, date_filter=None, start_date=None, end_date=None):
        """
        Get start and end dates based on filter parameters
        
        Args:
            filter_period: 'day', 'week', 'month', 'custom', or None
            date_filter: Specific date string in 'Y-m-d' format
            start_date: Start date string for custom range
            end_date: End date string for custom range
            
        Returns:
            Tuple of (start_date, end_date) as date objects
        """
        today = timezone.localdate()

        if filter_period == 'day' and date_filter:
            date_obj = timezone.datetime.strptime(date_filter, '%Y-%m-%d').date()
            return date_obj, date_obj
        elif filter_period == 'week':
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            return start_of_week, end_of_week
        elif filter_period == 'month':
            start_of_month = today.replace(day=1)
            end_of_month = (start_of_month + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            return start_of_month, end_of_month
        elif filter_period == 'custom' and start_date and end_date:
            start_date_obj = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_obj = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()
            return start_date_obj, end_date_obj
        else:
            # Default to today
            return today, today
    
    @staticmethod
    def get_filter_context(filter_period, date_filter, start_date, end_date):
        """
        Get context data for templates with proper default values
        
        Returns:
            Dictionary with filter context for templates
        """
        context = {
            'filter_period': filter_period,
            'current_date_filter': date_filter,
            'current_start_date': start_date,
            'current_end_date': end_date,
        }
        
        # Set default date filter for display if none provided
        if not any([filter_period, date_filter, start_date, end_date]):
            today = timezone.localdate()
            context['current_date_filter'] = today.strftime('%Y-%m-%d')
        
        return context


class DashboardService:
    """Service for dashboard data aggregation and business logic"""
    
    @staticmethod
    def get_dashboard_data(selected_account=None, transactions_page=1, transactions_per_page=10):
        """
        Get all dashboard data including accounts, transactions, and statistics
        
        Args:
            selected_account: FinancialAccount instance or None
            transactions_page: Page number for transactions
            transactions_per_page: Number of transactions per page
            
        Returns:
            Dictionary with dashboard context data
        """
        from apps.accounting.models import FinancialAccount
        from django.core.paginator import Paginator
        
        # Get active accounts
        accounts = FinancialAccount.objects.filter(is_active=True)
        
        # Get transactions for selected account with pagination
        transactions = []
        transactions_paginator = None
        transactions_page_obj = None
        
        if selected_account:
            all_transactions = DashboardService._get_account_transactions(selected_account)
        else:
            # Show recent transactions from all accounts when no specific account is selected
            all_transactions = DashboardService._get_recent_all_transactions()
            
        transactions_paginator = Paginator(all_transactions, transactions_per_page)
        transactions_page_obj = transactions_paginator.get_page(transactions_page)
        transactions = transactions_page_obj.object_list
        
        # Calculate statistics
        stats = DashboardService._calculate_account_statistics(accounts)
        
        return {
            'accounts': accounts,
            'selected_account': selected_account,
            'transactions': transactions,
            'transactions_paginator': transactions_paginator,
            'transactions_page_obj': transactions_page_obj,
            'stats': stats
        }
    
    @staticmethod
    def _get_account_transactions(account):
        """Get all transactions for a specific account"""
        from apps.sales.models import Sale
        from apps.accounting.models import Expenditure
        from apps.contacts.models import AgentPayment
        
        transactions = []
        
        # Get client sales paid directly to this account
        client_sales = Sale.objects.filter(
            paid_to_account=account,
            agent__isnull=True  # Only direct client sales
        ).select_related('related_acquisition__ticket')
        
        for sale in client_sales:
            ticket_desc = (sale.related_acquisition.ticket.get_ticket_type_display() 
                         if sale.related_acquisition and sale.related_acquisition.ticket 
                         else "Unknown Ticket")
            
            transactions.append({
                'date': sale.sale_date,
                'type': 'Sotuv (Mijoz)',
                'description': f"{ticket_desc} - {sale.client_full_name or 'N/A'}",
                'amount': sale.total_sale_amount,
                'currency': sale.sale_currency,
                'balance_effect': 'income'
            })
        
        # Get agent payments to this account
        agent_payments = AgentPayment.objects.filter(
            paid_to_account=account
        ).select_related('agent')
        
        for payment in agent_payments:
            transactions.append({
                'date': payment.payment_date,
                'type': 'Agent To\'lovi',
                'description': f"Agent: {payment.agent.name}",
                'amount': payment.amount,
                'currency': payment.currency,
                'balance_effect': 'income'
            })
        
        # Get supplier payments from this account
        from apps.contacts.models import SupplierPayment
        supplier_payments = SupplierPayment.objects.filter(
            paid_from_account=account
        ).select_related('supplier')
        
        for payment in supplier_payments:
            transactions.append({
                'date': payment.payment_date,
                'type': 'Ta\'minotchi To\'lovi',
                'description': f"Ta'minotchi: {payment.supplier.name}",
                'amount': payment.amount,
                'currency': payment.currency,
                'balance_effect': 'expense'
            })
        
        # Get general expenditures from this account (exclude supplier payments)
        expenditures = Expenditure.objects.filter(
            paid_from_account=account,
            expenditure_type=Expenditure.ExpenditureType.GENERAL
        )
        
        for exp in expenditures:
            transactions.append({
                'date': exp.expenditure_date,
                'type': 'Umumiy Xarajat',
                'description': exp.description,
                'amount': exp.amount,
                'currency': exp.currency,
                'balance_effect': 'expense'
            })
        
        # Sort by date, most recent first
        transactions.sort(key=lambda t: t['date'], reverse=True)
        
        return transactions
    
    @staticmethod
    def _get_recent_all_transactions(limit_days=30):
        """Get recent transactions from all accounts when no specific account is selected"""
        from apps.sales.models import Sale
        from apps.accounting.models import Expenditure
        from apps.contacts.models import AgentPayment, SupplierPayment
        from datetime import timedelta
        
        # Get date limit
        date_limit = timezone.now() - timedelta(days=limit_days)
        transactions = []
        
        # Get recent client sales
        client_sales = Sale.objects.filter(
            sale_date__gte=date_limit,
            agent__isnull=True  # Only direct client sales
        ).select_related('related_acquisition__ticket', 'paid_to_account')
        
        for sale in client_sales:
            ticket_desc = (sale.related_acquisition.ticket.get_ticket_type_display() 
                         if sale.related_acquisition and sale.related_acquisition.ticket 
                         else "Unknown Ticket")
            
            transactions.append({
                'date': sale.sale_date,
                'type': 'Sotuv (Mijoz)',
                'description': f"{ticket_desc} - {sale.client_full_name or 'N/A'}",
                'amount': sale.total_sale_amount,
                'currency': sale.sale_currency,
                'balance_effect': 'income',
                'account': sale.paid_to_account.name if sale.paid_to_account else 'N/A'
            })
        
        # Get recent agent payments
        agent_payments = AgentPayment.objects.filter(
            payment_date__gte=date_limit
        ).select_related('agent', 'paid_to_account')
        
        for payment in agent_payments:
            transactions.append({
                'date': payment.payment_date,
                'type': 'Agent To\'lovi',
                'description': f"Agent: {payment.agent.name}",
                'amount': payment.amount,
                'currency': payment.currency,
                'balance_effect': 'income',
                'account': payment.paid_to_account.name if payment.paid_to_account else 'N/A'
            })
        
        # Get recent supplier payments
        supplier_payments = SupplierPayment.objects.filter(
            payment_date__gte=date_limit
        ).select_related('supplier', 'paid_from_account')
        
        for payment in supplier_payments:
            transactions.append({
                'date': payment.payment_date,
                'type': 'Ta\'minotchi To\'lovi',
                'description': f"Ta'minotchi: {payment.supplier.name}",
                'amount': payment.amount,
                'currency': payment.currency,
                'balance_effect': 'expense',
                'account': payment.paid_from_account.name if payment.paid_from_account else 'N/A'
            })
        
        # Get recent expenditures
        expenditures = Expenditure.objects.filter(
            expenditure_date__gte=date_limit,
            expenditure_type=Expenditure.ExpenditureType.GENERAL
        ).select_related('paid_from_account')
        
        for exp in expenditures:
            transactions.append({
                'date': exp.expenditure_date,
                'type': 'Umumiy Xarajat',
                'description': exp.description,
                'amount': exp.amount,
                'currency': exp.currency,
                'balance_effect': 'expense',
                'account': exp.paid_from_account.name if exp.paid_from_account else 'N/A'
            })
        
        # Sort by date, most recent first
        transactions.sort(key=lambda t: t['date'], reverse=True)
        
        return transactions
    
    @staticmethod
    def _calculate_account_statistics(accounts):
        """Calculate comprehensive account statistics"""
        if not accounts:
            return {
                'total_count': 0,
                'positive_count': 0,
                'total_uzs': Decimal('0.00'),
                'total_usd': Decimal('0.00'),
                'currency_count': 0,
                'negative_count': 0
            }
        
        uzs_total = Decimal('0.00')
        usd_total = Decimal('0.00')
        positive_count = 0
        negative_count = 0
        currencies = set()
        
        for account in accounts:
            if account.current_balance > 0:
                positive_count += 1
            elif account.current_balance < 0:
                negative_count += 1
            
            if account.currency == 'UZS':
                uzs_total += account.current_balance
            elif account.currency == 'USD':
                usd_total += account.current_balance
            
            currencies.add(account.currency)
        
        return {
            'total_count': len(accounts),
            'positive_count': positive_count,
            'negative_count': negative_count,
            'total_uzs': uzs_total,
            'total_usd': usd_total,
            'currency_count': len(currencies)
        } 