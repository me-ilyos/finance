from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from apps.contacts.models import Supplier
from apps.accounting.models import FinancialAccount
from decimal import Decimal


class Ticket(models.Model):
    class TicketType(models.TextChoices):
        AIR_TICKET = 'AIR', 'Air Ticket'
        TOUR_TICKET = 'TOUR', 'Tour Ticket'

    ticket_type = models.CharField(max_length=4, choices=TicketType.choices)
    identifier = models.CharField(max_length=255, unique=True, blank=True, help_text="Unique identifier for this ticket type/batch. Auto-generated if left blank.")
    description = models.TextField(help_text="E.g., Destination for air ticket, name/details for tour ticket")
    departure_date_time = models.DateTimeField()
    arrival_date_time = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.identifier:
            parts = [self.get_ticket_type_display().upper().replace(" ", "_")]
            if self.description:
                slugified_desc = slugify(self.description)
                parts.append(slugified_desc[:50] if len(slugified_desc) > 50 else slugified_desc)
            if self.departure_date_time:
                parts.append(self.departure_date_time.strftime('%Y%m%d%H%M'))
            self.identifier = "-".join(filter(None, parts))
            
            original_identifier = self.identifier
            counter = 1
            while Ticket.objects.filter(identifier=self.identifier).exclude(pk=self.pk).exists():
                self.identifier = f"{original_identifier}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.identifier

class Acquisition(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='acquisitions')
    ticket = models.ForeignKey(Ticket, on_delete=models.PROTECT, related_name='acquisitions')
    acquisition_date = models.DateField()
    initial_quantity = models.PositiveIntegerField(help_text="Initial quantity acquired in this batch.")
    available_quantity = models.PositiveIntegerField(help_text="Available quantity from this batch for sale. Updated by sales operations.", default=0, editable=False)

    class Currency(models.TextChoices):
        UZS = 'UZS', 'Uzbek Som'
        USD = 'USD', 'US Dollar'

    # Prices are per unit
    unit_price_uzs = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    unit_price_usd = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    
    transaction_currency = models.CharField(max_length=3, choices=Currency.choices, help_text="Currency of this transaction (unit price and total)")

    # Total amount can be calculated, but storing it can be useful for records
    # We'll ensure this is based on transaction_currency via a clean method or signals later
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, editable=False, help_text="Automatically calculated based on original quantity and unit price.")
    
    paid_from_account = models.ForeignKey(
        FinancialAccount, 
        on_delete=models.PROTECT, 
        related_name='acquisitions_paid', 
        blank=True,  # Allow to be empty
        null=True    # Allow to be empty in DB
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if self.transaction_currency == self.Currency.UZS:
            if not self.unit_price_uzs:
                raise ValidationError({'unit_price_uzs': 'Unit price in UZS must be provided if transaction currency is UZS.'})
            if self.unit_price_usd:
                self.unit_price_usd = None # Ensure other currency price is cleared
        elif self.transaction_currency == self.Currency.USD:
            if not self.unit_price_usd:
                raise ValidationError({'unit_price_usd': 'Unit price in USD must be provided if transaction currency is USD.'})
            if self.unit_price_uzs:
                self.unit_price_uzs = None # Ensure other currency price is cleared
        else:
            raise ValidationError('Transaction currency must be set.')
        
        # Validate paid_from_account currency if account is selected
        if self.paid_from_account and self.paid_from_account.currency != self.transaction_currency:
            raise ValidationError({
                'paid_from_account': f"The currency of the selected payment account ({self.paid_from_account.currency}) "
                                     f"does not match the transaction currency ({self.transaction_currency})."
            })

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        _original_initial_quantity = 0
        _original_available_quantity = 0 # Used if initial_quantity changes on an existing record

        if not is_new:
            try:
                original_instance = Acquisition.objects.get(pk=self.pk)
                _original_initial_quantity = original_instance.initial_quantity
                _original_available_quantity = original_instance.available_quantity
                # For financial calculations
                original_paid_from_account_id = original_instance.paid_from_account_id
                original_total_amount_for_payment = original_instance.total_amount
            except Acquisition.DoesNotExist:
                is_new = True # Treat as new if original somehow vanished
                original_paid_from_account_id = None # Ensure these are reset
                original_total_amount_for_payment = Decimal('0.00')
        else:
            original_paid_from_account_id = None
            original_total_amount_for_payment = Decimal('0.00')


        # Calculate total_amount based on the initial_quantity
        if self.transaction_currency == self.Currency.UZS and self.unit_price_uzs is not None:
            self.total_amount = self.initial_quantity * self.unit_price_uzs
        elif self.transaction_currency == self.Currency.USD and self.unit_price_usd is not None:
            self.total_amount = self.initial_quantity * self.unit_price_usd
        else:
            self.total_amount = Decimal('0.00')
        
        if is_new:
            self.available_quantity = self.initial_quantity # Set available from initial on creation
        else:
            # If initial quantity changed on an existing record, adjust available quantity
            if self.initial_quantity != _original_initial_quantity:
                quantity_diff = self.initial_quantity - _original_initial_quantity
                # Adjust available quantity, ensuring it's not negative or more than new initial quantity
                self.available_quantity = max(0, min(self.initial_quantity, _original_available_quantity + quantity_diff))
            # If initial_quantity didn't change, available_quantity is preserved (it's managed by sales or other processes)

        # Financial account update logic (largely unchanged, but relies on correct total_amount)
        # Renamed local variables for clarity in this scope
        _current_paid_from_account_id = self.paid_from_account_id if self.paid_from_account else None

        with transaction.atomic():
            # Revert payment from old account if account changed or total_amount changed
            if not is_new and original_paid_from_account_id and \
               (original_paid_from_account_id != _current_paid_from_account_id or original_total_amount_for_payment != self.total_amount):
                try:
                    old_account = FinancialAccount.objects.get(pk=original_paid_from_account_id)
                    old_account.current_balance += original_total_amount_for_payment
                    old_account.save()
                except FinancialAccount.DoesNotExist:
                    # Log this error or handle appropriately
                    pass 
            
            super().save(*args, **kwargs) # Save the Acquisition instance itself

            # Deduct payment from new/current account if account is set and
            # (it's a new acquisition or account/total_amount changed)
            if self.paid_from_account and \
               (is_new or (original_paid_from_account_id != _current_paid_from_account_id or original_total_amount_for_payment != self.total_amount)):
                self.paid_from_account.current_balance -= self.total_amount
                self.paid_from_account.save()

    def __str__(self):
        ticket_identifier = self.ticket.identifier if self.ticket and hasattr(self.ticket, 'identifier') and self.ticket.identifier else f"Ticket ID: {self.ticket_id}"
        return f"Acquisition of {self.ticket.description if self.ticket else 'N/A'}: {self.initial_quantity} bought, {self.available_quantity} available (ID: {ticket_identifier}) from {self.supplier.name}"
