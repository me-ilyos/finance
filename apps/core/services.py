from django.utils import timezone
from datetime import timedelta


class DateFilterService:
    """Simple utility service for date filtering logic across the application"""
    
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