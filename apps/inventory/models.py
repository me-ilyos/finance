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
    quantity = models.PositiveIntegerField(help_text="Currently available quantity from this batch.")
    
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

        # Calculate total_amount based on the *original* quantity intended for this field if it were just total acquired.
        # Since self.quantity now means *available*, total_amount should be based on the initial input quantity.
        # This requires a bit of care. If quantity is editable in admin, this might get tricky.
        # For now, we assume total_amount is calculated based on the quantity field at the point of save for this batch definition.
        if self.transaction_currency == self.Currency.UZS and self.unit_price_uzs is not None:
            self.total_amount = self.quantity * self.unit_price_uzs # This might need adjustment if quantity is edited later
        elif self.transaction_currency == self.Currency.USD and self.unit_price_usd is not None:
            self.total_amount = self.quantity * self.unit_price_usd # Same here
        else:
            self.total_amount = 0 
        
        # No need to initialize available_quantity separately anymore

        original_paid_from_account_id = None
        original_total_amount_for_payment = Decimal('0.00') # Use a distinct variable for payment part
        is_update_for_payment = self.pk is not None and not is_new 

        if is_update_for_payment:
            try:
                original_instance = Acquisition.objects.get(pk=self.pk)
                original_paid_from_account_id = original_instance.paid_from_account_id
                # original_total_amount for payment should be based on ITS total_amount, not current calculation
                original_total_amount_for_payment = original_instance.total_amount 
            except Acquisition.DoesNotExist:
                is_update_for_payment = False 

        with transaction.atomic():
            super().save(*args, **kwargs) 

            if is_update_for_payment and original_paid_from_account_id and \
               (original_paid_from_account_id != self.paid_from_account_id or original_total_amount_for_payment != self.total_amount):
                try:
                    old_account = FinancialAccount.objects.get(pk=original_paid_from_account_id)
                    old_account.current_balance += original_total_amount_for_payment
                    old_account.save()
                except FinancialAccount.DoesNotExist:
                    pass 
            
            if self.paid_from_account and \
               (is_new or (is_update_for_payment and (original_paid_from_account_id != self.paid_from_account_id or original_total_amount_for_payment != self.total_amount))):
                self.paid_from_account.current_balance -= self.total_amount
                self.paid_from_account.save()

    def __str__(self):
        ticket_identifier = self.ticket.identifier if self.ticket and hasattr(self.ticket, 'identifier') and self.ticket.identifier else f"Ticket ID: {self.ticket_id}"
        # quantity now directly represents available quantity
        return f"Acquisition of {self.ticket.description if self.ticket else 'N/A'}: {self.quantity} available (ID: {ticket_identifier}) from {self.supplier.name}"

    # Consider adding a clean method here to validate that:
    # 1. Either unit_price_uzs OR unit_price_usd is provided based on transaction_currency.
    # 2. total_amount matches quantity * unit_price (in transaction_currency).
    # 3. paid_from_account.currency matches transaction_currency.
