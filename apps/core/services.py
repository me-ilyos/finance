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
    def get_dashboard_data(selected_account=None):
        """
        Get all dashboard data including accounts, transactions, and statistics
        
        Args:
            selected_account: FinancialAccount instance or None
            
        Returns:
            Dictionary with dashboard context data
        """
        from apps.accounting.models import FinancialAccount
        
        # Get active accounts
        accounts = FinancialAccount.objects.filter(is_active=True)
        
        # Get transactions for selected account
        transactions = []
        if selected_account:
            transactions = DashboardService._get_account_transactions(selected_account)
        
        # Calculate statistics
        stats = DashboardService._calculate_account_statistics(accounts)
        
        return {
            'accounts': accounts,
            'selected_account': selected_account,
            'transactions': transactions,
            'stats': stats
        }
    
    @staticmethod
    def _get_account_transactions(account):
        """Get all transactions for a specific account"""
        from apps.sales.models import Sale
        from apps.accounting.models import Expenditure
        
        transactions = []
        
        # Get sales paid to this account
        sales = Sale.objects.filter(
            paid_to_account=account
        ).select_related('agent', 'related_acquisition__ticket')
        
        for sale in sales:
            buyer_name = sale.agent.name if sale.agent else sale.client_full_name
            ticket_desc = (sale.related_acquisition.ticket.get_ticket_type_display() 
                         if sale.related_acquisition and sale.related_acquisition.ticket 
                         else "Unknown Ticket")
            
            amount = (sale.paid_amount_on_this_sale 
                     if sale.agent 
                     else sale.total_sale_amount)
            
            transactions.append({
                'date': sale.sale_date,
                'type': 'Sotuv',
                'description': f"{ticket_desc} - {buyer_name}",
                'amount': amount,
                'currency': sale.sale_currency,
                'balance_effect': 'income'
            })
        
        # Get expenditures from this account
        expenditures = Expenditure.objects.filter(paid_from_account=account)
        
        for exp in expenditures:
            transactions.append({
                'date': exp.expenditure_date,
                'type': 'Xarajat',
                'description': exp.description,
                'amount': exp.amount,
                'currency': exp.currency,
                'balance_effect': 'expense'
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