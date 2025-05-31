from django.db import models


class CurrencyChoices(models.TextChoices):
    """Centralized currency choices for the entire application"""
    UZS = 'UZS', 'Uzbek Som'
    USD = 'USD', 'US Dollar'


class AccountTypeChoices(models.TextChoices):
    """Account type choices for financial accounts"""
    CASH = 'CASH', 'Cash'
    CARD = 'CARD', 'Card'
    BANK_ACCOUNT = 'BANK_ACCOUNT', 'Bank Account'


class TicketTypeChoices(models.TextChoices):
    """Ticket type choices for inventory management"""
    AIR_TICKET = 'AIR_TICKET', 'Air Ticket'
    TOUR_TICKET = 'TOUR_TICKET', 'Tour Ticket' 