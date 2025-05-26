from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.inventory.models import Acquisition
from apps.contacts.models import Agent
from apps.accounting.models import FinancialAccount
from decimal import Decimal

class Sale(models.Model):
    # SaleCurrency choices are still useful for clarity, even if determined by acquisition
    class SaleCurrency(models.TextChoices):
        UZS = 'UZS', 'Uzbek Som'
        USD = 'USD', 'US Dollar'

    sale_date = models.DateTimeField(default=timezone.now)
    quantity = models.PositiveIntegerField()
    related_acquisition = models.ForeignKey(
        Acquisition, 
        on_delete=models.PROTECT,
        related_name='sales_from_this_batch'
    )

    agent = models.ForeignKey(Agent, on_delete=models.PROTECT, null=True, blank=True, related_name='agent_sales')
    client_full_name = models.CharField(max_length=255, null=True, blank=True)
    client_id_number = models.CharField(max_length=50, null=True, blank=True)

    unit_sale_price = models.DecimalField(max_digits=15, decimal_places=2, help_text="Price per unit in the transaction currency.")
    # sale_currency will be same as related_acquisition.transaction_currency
    sale_currency = models.CharField(max_length=3, choices=SaleCurrency.choices, editable=False)
    total_sale_amount = models.DecimalField(max_digits=15, decimal_places=2, editable=False, help_text="Total amount for this sale.")
    
    # Profit is in the same currency as the transaction
    profit = models.DecimalField(max_digits=15, decimal_places=2, editable=False, default=Decimal('0.00'), help_text="Profit from this sale in transaction currency.")

    # Payment Information
    paid_to_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        null=True, 
        blank=True, 
        related_name='sale_payments_received',
        help_text="Account that received the payment for this sale."
    )
    # For partial payments or agent credit, we'll need a separate Payment model later.
    # is_fully_paid = models.BooleanField(default=False) # Future consideration

    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()

        # Determine sale_currency early if possible
        if self.related_acquisition:
            self.sale_currency = self.related_acquisition.transaction_currency
        # else: # If related_acquisition is not yet set, sale_currency cannot be determined here
            # The form should ensure related_acquisition is provided before this point for full validation
            # Or, the paid_to_account validation needs to be conditional on sale_currency being set.

        if self.agent and (self.client_full_name or self.client_id_number):
            raise ValidationError("Cannot specify both an agent and client details for the same sale.")
        if not self.agent and not (self.client_full_name and self.client_id_number):
            raise ValidationError("Must specify either an agent or both client full name and ID number.")
        if not self.agent and self.client_full_name and not self.client_id_number:
            raise ValidationError("Client ID number is required if client full name is provided.")
        if not self.agent and not self.client_full_name and self.client_id_number:
            raise ValidationError("Client full name is required if client ID number is provided.")

        if self.related_acquisition:
            # Effective available quantity for this sale/update
            effective_available_qty = self.related_acquisition.available_quantity
            if self.pk: # if updating an existing sale
                original_sale = Sale.objects.get(pk=self.pk)
                if self.related_acquisition_id == original_sale.related_acquisition_id:
                    # Add back the quantity from the original state of *this* sale before checking
                    effective_available_qty += original_sale.quantity
            
            if self.quantity > effective_available_qty:
                raise ValidationError({
                    'quantity': f"Cannot sell {self.quantity}. Only {effective_available_qty} effectively available from the selected batch for this sale/update."
                })
        
        # Validate paid_to_account currency only if sale_currency is determined
        if self.paid_to_account and self.sale_currency: # Check if sale_currency is now set
            if self.paid_to_account.currency != self.sale_currency:
                raise ValidationError({
                    'paid_to_account': f"The currency of the selected payment account ({self.paid_to_account.currency}) "
                                         f"does not match the determined sale currency ({self.sale_currency})."
                })
        elif self.paid_to_account and not self.sale_currency:
            # This might happen if related_acquisition is not selected yet in the form
            raise ValidationError({
                'paid_to_account': "Cannot validate payment account currency until the sale currency is determined (select an acquisition)."
            })

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        original_quantity = 0
        original_related_acquisition_id = None
        original_total_sale_amount = Decimal('0.00')
        original_paid_to_account_id = None

        if not is_new:
            try:
                original_sale = Sale.objects.select_related('related_acquisition', 'paid_to_account').get(pk=self.pk)
                original_quantity = original_sale.quantity
                original_related_acquisition_id = original_sale.related_acquisition_id
                original_total_sale_amount = original_sale.total_sale_amount
                original_paid_to_account_id = original_sale.paid_to_account_id
            except Sale.DoesNotExist:
                is_new = True 
        
        # 1. Determine Sale Currency & Calculate Total Sale Amount
        # sale_currency is now set in clean() if related_acquisition is present, or re-affirmed here
        if self.related_acquisition:
            self.sale_currency = self.related_acquisition.transaction_currency 
        else:
            # This should ideally be caught by form validation making related_acquisition mandatory
            raise ValueError("Related acquisition is mandatory to determine sale currency.")
            
        self.total_sale_amount = self.quantity * self.unit_sale_price

        # 2. Calculate Profit
        unit_cost_native = Decimal(0)
        if self.related_acquisition.transaction_currency == Acquisition.Currency.UZS:
            unit_cost_native = self.related_acquisition.unit_price_uzs or Decimal(0)
        elif self.related_acquisition.transaction_currency == Acquisition.Currency.USD:
            unit_cost_native = self.related_acquisition.unit_price_usd or Decimal(0)
        
        total_cost_for_sold_items = self.quantity * unit_cost_native
        self.profit = self.total_sale_amount - total_cost_for_sold_items # Profit in sale_currency

        with transaction.atomic():
            # 3. Update Stock (Acquisition.available_quantity)
            # Lock the related acquisition row
            current_acq_to_update = Acquisition.objects.select_for_update().get(pk=self.related_acquisition_id)

            if is_new:
                if self.quantity > current_acq_to_update.available_quantity:
                    raise ValidationError(f"Stock error (save): Tried to sell {self.quantity}, but only {current_acq_to_update.available_quantity} available.")
                current_acq_to_update.available_quantity -= self.quantity
            else: # Handle updates
                quantity_diff = self.quantity - original_quantity
                
                if original_related_acquisition_id and original_related_acquisition_id != self.related_acquisition_id:
                    # Acquisition changed: Revert stock on old, deduct from new
                    old_acq = Acquisition.objects.select_for_update().get(pk=original_related_acquisition_id)
                    old_acq.available_quantity += original_quantity
                    old_acq.save()
                    
                    if self.quantity > current_acq_to_update.available_quantity:
                        raise ValidationError(f"Stock error (save-acq changed): Tried to sell {self.quantity} from new batch, but only {current_acq_to_update.available_quantity} available.")
                    current_acq_to_update.available_quantity -= self.quantity
                elif quantity_diff != 0: # Same acquisition, quantity changed
                    # We need to ensure this adjustment doesn't make quantity negative based on its current state
                    if quantity_diff > 0 and quantity_diff > current_acq_to_update.available_quantity:
                         raise ValidationError(f"Stock error (save-qty increased): Tried to increase sale by {quantity_diff}, but only {current_acq_to_update.available_quantity} net available.")
                    # If quantity_diff < 0, we are returning stock, which should always be fine.
                    current_acq_to_update.available_quantity -= quantity_diff 
            
            current_acq_to_update.save()
            
            # Save the sale itself to ensure self.pk is available for financial account update if new
            super().save(*args, **kwargs) 

            # 4. Update Financial Account Balance for payment received
            # Revert effect on old account if account or amount changed during an update
            if not is_new and original_paid_to_account_id and \
               (original_paid_to_account_id != self.paid_to_account_id or original_total_sale_amount != self.total_sale_amount):
                try:
                    old_payment_account = FinancialAccount.objects.get(pk=original_paid_to_account_id)
                    old_payment_account.current_balance -= original_total_sale_amount # Subtract as it was an income
                    old_payment_account.save()
                except FinancialAccount.DoesNotExist:
                    pass # Log this ideally
            
            # Apply effect to new/current account if specified and details changed or it's new
            if self.paid_to_account and \
               (is_new or original_paid_to_account_id != self.paid_to_account_id or original_total_sale_amount != self.total_sale_amount):
                # Ensure paid_to_account is fresh if it was just set on a new instance or changed
                payment_account = FinancialAccount.objects.get(pk=self.paid_to_account_id)
                payment_account.current_balance += self.total_sale_amount # Add as it is an income
                payment_account.save()
            
            # If it was an agent sale and fully paid, could update agent balance to 0 for this sale amount
            # If agent sale and not paid (paid_to_account is None), update agent.outstanding_balance
            if self.agent:
                if self.paid_to_account: # Assuming if paid_to_account is set, it's fully paid for this sale
                    # If we were tracking per-sale debt, this would clear it. For now, no change to agent balance if paid.
                    pass 
                else: # Not paid or partially paid (handled by None for now) - increase outstanding balance
                    agent_to_update = Agent.objects.get(pk=self.agent_id)
                    if self.sale_currency == Sale.SaleCurrency.USD:
                        agent_to_update.outstanding_balance_usd += self.total_sale_amount
                    elif self.sale_currency == Sale.SaleCurrency.UZS:
                        agent_to_update.outstanding_balance_uzs += self.total_sale_amount
                    agent_to_update.save()
            # Note: Updating agent balance on sale *edit* (if payment status/amount changes) needs careful handling of old state.
            # The current logic adds to outstanding balance if paid_to_account is None. 
            # If a sale is edited from unpaid to paid, or vice-versa, or amount changes, this simple logic might double-count or miss.
            # A more robust agent payment system would involve separate Payment records linked to Sales. 
            # For now, this is a basic increment if no direct payment account is specified for an agent sale.

    def __str__(self):
        buyer_info = str(self.agent.name) if self.agent else f"{self.client_full_name or 'N/A Client'}"
        ticket_info = self.related_acquisition.ticket.identifier if self.related_acquisition and self.related_acquisition.ticket else f"Acq.ID: {self.related_acquisition_id}"
        sale_date_str = self.sale_date.strftime('%Y-%m-%d') if self.sale_date else 'N/A Date'
        profit_str = str(self.profit) if hasattr(self, 'profit') else "N/A"
        payment_status = "Paid" if self.paid_to_account else ("Owes" if self.agent else "Unpaid")
        return f"Sale: {self.quantity}x {ticket_info} to {buyer_info} on {sale_date_str} (Profit: {profit_str} {self.sale_currency}) - {payment_status}"
