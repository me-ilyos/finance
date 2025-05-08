from django.db import models
from django.utils import timezone
from apps.stock.models import TicketPurchase


class Agent(models.Model):
    """Represents an agent who buys tickets"""

    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class Seller(models.Model):
    """Represents an employee who sells tickets"""

    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class TicketSale(models.Model):
    """Records the sale of tickets to a customer or agent"""

    CUSTOMER_TYPES = (
        ("individual", "Individual Customer"),
        ("agent", "Agent"),
    )

    CURRENCY_CHOICES = (
        ("UZS", "Uzbekistan Som"),
        ("USD", "US Dollar"),
    )

    sale_id = models.CharField(max_length=50, unique=True, editable=False)
    sale_date = models.DateTimeField(default=timezone.now)
    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPES)
    customer_name = models.CharField(
        max_length=255,
        help_text="Name of individual customer if not an agent",
        blank=True,
        null=True,
    )
    agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name="ticket_sales",
        blank=True,
        null=True,
    )
    seller = models.ForeignKey(
        Seller, on_delete=models.CASCADE, related_name="ticket_sales"
    )
    ticket_purchase = models.ForeignKey(
        TicketPurchase, on_delete=models.CASCADE, related_name="ticket_sales"
    )
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="UZS")
    notes = models.TextField(blank=True, null=True)

    # Calculated fields
    profit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Will be null if currencies don't match",
    )

    @property
    def total_price(self):
        return self.quantity * self.unit_price

    def save(self, *args, **kwargs):
        if not self.sale_id:
            # Generate a sale ID if one doesn't exist
            # Format: TS-YYYYMMDD-XXXX (TS for Ticket Sale)
            today = timezone.now().strftime("%Y%m%d")
            today_start = timezone.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            today_sales = TicketSale.objects.filter(sale_date__gte=today_start).count()

            # Create sale ID with sequential number for today
            self.sale_id = f"TS-{today}-{today_sales + 1:04d}"

        # Calculate profit if currencies match
        if self.ticket_purchase and self.currency == self.ticket_purchase.currency:
            purchase_unit_price = self.ticket_purchase.unit_price
            self.profit = (self.unit_price - purchase_unit_price) * self.quantity
        else:
            self.profit = None

        super().save(*args, **kwargs)

    def __str__(self):
        if self.customer_type == "agent" and self.agent:
            customer = self.agent.name
        else:
            customer = self.customer_name
        return f"Sale {self.sale_id} - {customer}"

    class Meta:
        ordering = ["-sale_date"]
        verbose_name = "Ticket Sale"
        verbose_name_plural = "Ticket Sales"


class Payment(models.Model):
    """Records payments for ticket sales"""
    
    PAYMENT_TYPES = (
        ("full", "Full Payment"),
        ("partial", "Partial Payment"),
    )
    
    payment_id = models.CharField(max_length=50, unique=True, editable=False)
    payment_date = models.DateTimeField(default=timezone.now)
    ticket_sale = models.ForeignKey(
        TicketSale, on_delete=models.CASCADE, related_name="payments"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(
        max_length=3, 
        choices=TicketSale.CURRENCY_CHOICES, 
        default="UZS"
    )
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES, default="full")
    notes = models.TextField(blank=True, null=True)
    
    def save(self, *args, **kwargs):
        if not self.payment_id:
            # Generate a payment ID if one doesn't exist
            # Format: PMT-YYYYMMDD-XXXX (PMT for Payment)
            today = timezone.now().strftime("%Y%m%d")
            today_start = timezone.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            today_payments = Payment.objects.filter(payment_date__gte=today_start).count()

            # Create payment ID with sequential number for today
            self.payment_id = f"PMT-{today}-{today_payments + 1:04d}"
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Payment {self.payment_id} for {self.ticket_sale.sale_id}"
    
    class Meta:
        ordering = ["-payment_date"]
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
