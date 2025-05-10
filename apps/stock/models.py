from django.db import models
from django.utils import timezone
import uuid


class Supplier(models.Model):
    name = models.CharField(max_length=255, verbose_name="Nomi")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan sana")

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]
        verbose_name = "Ta'minotchi"
        verbose_name_plural = "Ta'minotchilar"


class TicketPurchase(models.Model):
    CURRENCY_CHOICES = (
        ("UZS", "O'zbek so'mi"),
        ("USD", "AQSH dollari"),
    )

    purchase_id = models.CharField(max_length=50, unique=True, editable=False, verbose_name="Xarid ID")
    purchase_date = models.DateTimeField(default=timezone.now, verbose_name="Xarid sanasi")
    supplier = models.ForeignKey(
        Supplier, on_delete=models.CASCADE, related_name="ticket_purchases", verbose_name="Ta'minotchi"
    )
    commentary = models.TextField(blank=True, null=True, verbose_name="Izohlar")
    quantity = models.PositiveIntegerField(verbose_name="Miqdori")
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Narxi")
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="UZS", verbose_name="Valyuta")
    quantity_sold = models.PositiveIntegerField(default=0, editable=False, verbose_name="Sotilgan miqdor")  # Track sold tickets

    def __str__(self):
        return f"Xarid {self.purchase_id} - {self.supplier.name}"

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
        verbose_name = "Chipta xaridi"
        verbose_name_plural = "Chipta xaridlari"
