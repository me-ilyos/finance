from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.inventory.models import Acquisition
# from apps.contacts.models import Agent # Removed direct import, will use apps.get_model
from django.apps import apps # Added for apps.get_model
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

    agent = models.ForeignKey(
        'contacts.Agent', # Use string reference here
        on_delete=models.PROTECT, 
        null=True, 
        blank=True, 
        related_name='agent_sales'
    )
    client_full_name = models.CharField(max_length=255, null=True, blank=True)
    client_id_number = models.CharField(max_length=50, null=True, blank=True)

    unit_sale_price = models.DecimalField(max_digits=15, decimal_places=2, help_text="Price per unit in the transaction currency.")
    # sale_currency will be same as related_acquisition.transaction_currency
    sale_currency = models.CharField(max_length=3, choices=SaleCurrency.choices, editable=False)
    total_sale_amount = models.DecimalField(max_digits=15, decimal_places=2, editable=False, help_text="Total amount for this sale.")
    
    # Profit is in the same currency as the transaction
    profit = models.DecimalField(max_digits=15, decimal_places=2, editable=False, default=Decimal('0.00'), help_text="Profit from this sale in transaction currency.")

    # Specific payment tracking for this sale
    paid_amount_on_this_sale = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Total amount paid specifically towards this sale (including initial payment for agents)."
    )

    # Payment Information
    paid_to_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        null=True, 
        blank=True, 
        related_name='sale_payments_received',
        help_text="Account that received the payment (full for client, initial for agent)."
    )
    initial_payment_amount = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        help_text="Agent uchun boshlang'ich to'lov miqdori (sotuv valyutasida). Mijozlar uchun ishlatilmaydi."
    )
    # For partial payments or agent credit, we'll need a separate Payment model later.
    # is_fully_paid = models.BooleanField(default=False) # Future consideration

    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def balance_due_on_this_sale(self):
        return self.total_sale_amount - self.paid_amount_on_this_sale

    @property
    def is_fully_paid(self):
        if self.agent: # For agent sales, specifically check against paid_amount_on_this_sale
            return self.balance_due_on_this_sale <= Decimal('0.00')
        else: # For client sales, paid_to_account implies full payment of total_sale_amount
            return self.paid_to_account is not None

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

    def save(self, *args, _prevent_agent_payment_recursion=False, **kwargs):
        is_new = self.pk is None
        original_quantity = 0
        original_related_acquisition_id = None
        original_total_sale_amount = Decimal('0.00')
        original_paid_to_account_id = None
        original_agent_id = None
        original_sale_currency_for_agent_debt = None
        original_initial_payment_amount = None
        original_paid_amount_on_this_sale_val = None

        if not is_new:
            try:
                original_sale = Sale.objects.select_related('related_acquisition', 'paid_to_account', 'agent').get(pk=self.pk)
                original_quantity = original_sale.quantity
                original_related_acquisition_id = original_sale.related_acquisition_id
                original_total_sale_amount = original_sale.total_sale_amount
                original_paid_to_account_id = original_sale.paid_to_account_id
                original_initial_payment_amount = original_sale.initial_payment_amount or Decimal('0.00') # Ensure Decimal
                # Store original_paid_amount_on_this_sale to correctly adjust if initial_payment changes
                original_paid_amount_on_this_sale_val = original_sale.paid_amount_on_this_sale
                original_agent_id = original_sale.agent_id
                if original_sale.agent:
                    original_sale_currency_for_agent_debt = original_sale.sale_currency
            except Sale.DoesNotExist:
                is_new = True 
                original_initial_payment_amount = Decimal('0.00') # For consistency if treated as new
                original_paid_amount_on_this_sale_val = Decimal('0.00')
        
        AgentModel = apps.get_model('contacts', 'Agent') # Get Agent model dynamically

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

        # Determine/Initialize paid_amount_on_this_sale
        if not is_new:
            # For updates, self.paid_amount_on_this_sale is already loaded
            # with its current value. It will be adjusted by AgentPayment.save() if the
            # initial_payment_amount (and thus the auto AgentPayment) changes, or by new manual AgentPayments.
            # No direct assignment here for updates of this specific field before super.save().
            pass
        elif self.agent: # New agent sale
             # Initialize to 0. The auto-created AgentPayment for the initial_payment_amount (if any)
             # will add to this via its save() method.
            self.paid_amount_on_this_sale = Decimal('0.00')
        elif not self.agent and self.paid_to_account: # New, paid client sale
            self.paid_amount_on_this_sale = self.total_sale_amount
        else: # New, unpaid client sale OR new agent sale with no initial_payment (covered by self.agent case)
            self.paid_amount_on_this_sale = Decimal('0.00')
        
        # print(f"DEBUG Sale Save: PK {self.pk}, is_new {is_new}, Initialized paid_amount_on_this_sale: {self.paid_amount_on_this_sale}")

        with transaction.atomic():
            # 3. Update Stock (Acquisition.available_quantity)
            current_acq_to_update = Acquisition.objects.select_for_update().get(pk=self.related_acquisition_id)
            if is_new:
                if self.quantity > current_acq_to_update.available_quantity:
                    raise ValidationError(f"Stock error (save): Tried to sell {self.quantity}, but only {current_acq_to_update.available_quantity} available.")
                current_acq_to_update.available_quantity -= self.quantity
            else: # Handle updates for stock
                quantity_diff = self.quantity - original_quantity
                if original_related_acquisition_id and original_related_acquisition_id != self.related_acquisition_id:
                    old_acq = Acquisition.objects.select_for_update().get(pk=original_related_acquisition_id)
                    old_acq.available_quantity += original_quantity
                    old_acq.save()
                    if self.quantity > current_acq_to_update.available_quantity:
                        raise ValidationError(f"Stock error (save-acq changed): Tried to sell {self.quantity} from new batch, but only {current_acq_to_update.available_quantity} available.")
                    current_acq_to_update.available_quantity -= self.quantity
                elif quantity_diff != 0:
                    if quantity_diff > 0 and quantity_diff > current_acq_to_update.available_quantity:
                         raise ValidationError(f"Stock error (save-qty increased): Tried to increase sale by {quantity_diff}, but only {current_acq_to_update.available_quantity} net available.")
                    current_acq_to_update.available_quantity -= quantity_diff 
            current_acq_to_update.save()
            
            # Save the sale instance itself (includes paid_amount_on_this_sale from initial_payment)
            super().save(*args, **kwargs)

            # --- Agent and Financial Account Updates --- 
            # This section should only run if not called from AgentPayment.save()
            if not _prevent_agent_payment_recursion:
                AgentPaymentModel = apps.get_model('contacts', 'AgentPayment')
                current_initial_payment = self.initial_payment_amount or Decimal('0.00')

                # Simplified: Focus on creating/updating AgentPayment for the current sale's initial payment.
                # Complex revert logic for agent/amount changes needs careful thought and is deferred for now.

                if self.agent: 
                    agent_instance = AgentModel.objects.select_for_update().get(pk=self.agent_id)
                    
                    # Logic to adjust agent's overall balance based on the *gross* sale amount
                    # This happens regardless of initial payment, which is handled by AgentPayment
                    if is_new:
                        if self.sale_currency == 'UZS':
                            agent_instance.outstanding_balance_uzs += self.total_sale_amount
                        elif self.sale_currency == 'USD':
                            agent_instance.outstanding_balance_usd += self.total_sale_amount
                        agent_instance.save(update_fields=['outstanding_balance_uzs', 'outstanding_balance_usd', 'updated_at'])
                    elif not is_new:
                        # Revert old gross debt amount if agent or total sale amount/currency changed
                        if original_agent_id and original_agent_id == self.agent_id:
                            if original_sale_currency_for_agent_debt == 'UZS':
                                agent_instance.outstanding_balance_uzs -= original_total_sale_amount
                            elif original_sale_currency_for_agent_debt == 'USD':
                                agent_instance.outstanding_balance_usd -= original_total_sale_amount
                        elif original_agent_id and original_agent_id != self.agent_id:
                            # Agent changed, revert from old agent
                            try:
                                old_agent_instance = AgentModel.objects.select_for_update().get(pk=original_agent_id)
                                if original_sale_currency_for_agent_debt == 'UZS':
                                    old_agent_instance.outstanding_balance_uzs -= original_total_sale_amount
                                elif original_sale_currency_for_agent_debt == 'USD':
                                    old_agent_instance.outstanding_balance_usd -= original_total_sale_amount
                                old_agent_instance.save(update_fields=['outstanding_balance_uzs', 'outstanding_balance_usd', 'updated_at'])
                            except AgentModel.DoesNotExist:
                                pass # Old agent might have been deleted

                        # Apply new gross debt amount to current agent
                        if self.sale_currency == 'UZS':
                            agent_instance.outstanding_balance_uzs += self.total_sale_amount
                        elif self.sale_currency == 'USD':
                            agent_instance.outstanding_balance_usd += self.total_sale_amount
                        agent_instance.save(update_fields=['outstanding_balance_uzs', 'outstanding_balance_usd', 'updated_at'])


                    # Auto-create/update AgentPayment for the initial_payment_amount
                    if current_initial_payment > 0 and self.paid_to_account:
                        # Try to find an existing auto-generated payment for this sale
                        # This assumes only one such payment should exist per sale.
                        agent_payment, created_ap = AgentPaymentModel.objects.update_or_create(
                            related_sale_id=self.id, # Changed from sale_id
                            is_auto_payment_for_sale=True, 
                            defaults={
                                'agent': self.agent,
                                'payment_date': self.sale_date,
                                'paid_to_account': self.paid_to_account,
                                'notes': f"Avtomatik boshlang\'ich to\'lov (Sotuv ID: {self.id}). Payment method: auto_initial.",
                                **({'amount_paid_uzs': current_initial_payment} if self.sale_currency == 'UZS' else {'amount_paid_usd': current_initial_payment})
                            }
                        )
                        if not created_ap:
                            # If it was updated, its save method handles recalculations.
                            # If we force save here, it might re-trigger things if not careful.
                            # AgentPayment.save() should be idempotent or handle its own state.
                            # Let's assume AgentPayment.save() is robust. We explicitly call it if it's an update
                            # to ensure its logic (like financial account update) runs.
                            # However, update_or_create already calls save on the AgentPayment instance.
                            pass
                    else:
                        # If initial payment is zero or no account, ensure no auto-payment exists
                        AgentPaymentModel.objects.filter(related_sale_id=self.id, is_auto_payment_for_sale=True).delete() # Changed from sale_id

                # --- Client Financial Account Update (Direct Payment) ---
                elif not self.agent and self.paid_to_account: # Client sale with direct full payment
                    financial_account = FinancialAccount.objects.select_for_update().get(pk=self.paid_to_account_id)
                    if is_new:
                        financial_account.balance += self.total_sale_amount
                    else: # Update
                        # Revert old payment if account or amount changed
                        if original_paid_to_account_id and original_paid_to_account_id == self.paid_to_account_id:
                            financial_account.balance -= original_total_sale_amount # Revert previous amount from same account
                        elif original_paid_to_account_id and original_paid_to_account_id != self.paid_to_account_id:
                            try:
                                old_financial_account = FinancialAccount.objects.select_for_update().get(pk=original_paid_to_account_id)
                                old_financial_account.balance -= original_total_sale_amount
                                old_financial_account.save(update_fields=['balance', 'updated_at'])
                            except FinancialAccount.DoesNotExist:
                                pass # old account might have been deleted
                        
                        financial_account.balance += self.total_sale_amount # Add new amount
                    financial_account.save(update_fields=['balance', 'updated_at'])
                
                elif not self.agent and not self.paid_to_account and not is_new and original_paid_to_account_id:
                    # Client sale changed from paid to unpaid
                    try:
                        old_financial_account = FinancialAccount.objects.select_for_update().get(pk=original_paid_to_account_id)
                        old_financial_account.balance -= original_total_sale_amount
                        old_financial_account.save(update_fields=['balance', 'updated_at'])
                    except FinancialAccount.DoesNotExist:
                        pass

    def __str__(self):
        buyer_info = str(self.agent.name) if self.agent else f"{self.client_full_name or 'N/A Client'}"
        ticket_info = self.related_acquisition.ticket.identifier if self.related_acquisition and self.related_acquisition.ticket else f"Acq.ID: {self.related_acquisition_id}"
        sale_date_str = self.sale_date.strftime('%Y-%m-%d') if self.sale_date else 'N/A Date'
        profit_str = str(self.profit) if hasattr(self, 'profit') else "N/A"
        payment_status = "Paid" if self.paid_to_account else ("Owes" if self.agent else "Unpaid")
        return f"Sale: {self.quantity}x {ticket_info} to {buyer_info} on {sale_date_str} (Profit: {profit_str} {self.sale_currency}) - {payment_status}"

    def delete(self, *args, **kwargs):
        # Implement the delete logic here
        super().delete(*args, **kwargs)
