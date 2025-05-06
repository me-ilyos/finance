from django.db import models
from django.utils import timezone
import uuid


class Supplier(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class TicketPurchase(models.Model):
    CURRENCY_CHOICES = (
        ("UZS", "Uzbekistan Som"),
        ("USD", "US Dollar"),
    )

    purchase_id = models.CharField(max_length=50, unique=True, editable=False)
    purchase_date = models.DateTimeField(default=timezone.now)
    supplier = models.ForeignKey(
        Supplier, on_delete=models.CASCADE, related_name="ticket_purchases"
    )
    commentary = models.TextField(blank=True, null=True)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="UZS")
    quantity_sold = models.PositiveIntegerField(default=0, editable=False)  # Track sold tickets

    def __str__(self):
        return f"Purchase {self.purchase_id} - {self.supplier.name}"

    @property
    def total_price(self):
        return self.quantity * self.unit_price

    @property
    def quantity_remaining(self):
        return self.quantity - self.quantity_sold

    def save(self, *args, **kwargs):
        if not self.purchase_id:
            # Generate a purchase ID if one doesn't exist
            # Format: TP-YYYYMMDD-XXXX (TP for Ticket Purchase)
            today = timezone.now().strftime("%Y%m%d")
            # Get count of purchases made today
            today_start = timezone.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            today_purchases = TicketPurchase.objects.filter(
                purchase_date__gte=today_start
            ).count()

            # Create purchase ID with sequential number for today
            self.purchase_id = f"TP-{today}-{today_purchases + 1:04d}"

        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-purchase_date"]
        verbose_name = "Ticket Purchase"
        verbose_name_plural = "Ticket Purchases"
