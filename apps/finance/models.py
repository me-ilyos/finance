from django.db import models
from django.utils import timezone
from apps.stock.models import TicketPurchase


class Agent(models.Model):
    """Represents an agent who buys tickets"""

    name = models.CharField(max_length=255, verbose_name="Nomi")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan sana")

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]
        verbose_name = "Agent"
        verbose_name_plural = "Agentlar"


class Seller(models.Model):
    """Represents an employee who sells tickets"""

    name = models.CharField(max_length=255, verbose_name="Nomi")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan sana")

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]
        verbose_name = "Sotuvchi"
        verbose_name_plural = "Sotuvchilar"


class PaymentMethod(models.Model):
    """Represents a payment method used for receiving payments"""
    
    METHOD_TYPES = (
        ("plastic_card", "UZS Plastik Karta"),
        ("visa_card", "USD VISA Karta"),
        ("cash_uzs", "Naqd UZS"),
        ("cash_usd", "Naqd USD"),
        ("bank_account", "Bank Hisob Raqami"),
    )
    
    CURRENCY_CHOICES = (
        ("UZS", "O'zbek so'mi"),
        ("USD", "AQSH dollari"),
    )
    
    name = models.CharField(max_length=255, verbose_name="Nomi")
    method_type = models.CharField(max_length=20, choices=METHOD_TYPES, verbose_name="To'lov turi")
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, verbose_name="Valyuta")
    account_number = models.CharField(max_length=50, blank=True, null=True, 
                                     help_text="Karta yoki hisob raqami", verbose_name="Hisob raqami")
    details = models.TextField(blank=True, null=True, verbose_name="Qo'shimcha ma'lumot")
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan sana")
    
    def __str__(self):
        return f"{self.name} ({self.get_method_type_display()})"
    
    class Meta:
        ordering = ["name"]
        verbose_name = "To'lov usuli"
        verbose_name_plural = "To'lov usullari"


class TicketSale(models.Model):
    """Records the sale of tickets to a customer or agent"""

    CUSTOMER_TYPES = (
        ("individual", "Yakka mijoz"),
        ("agent", "Agent"),
    )

    CURRENCY_CHOICES = (
        ("UZS", "O'zbek so'mi"),
        ("USD", "AQSH dollari"),
    )

    sale_id = models.CharField(max_length=50, unique=True, editable=False, verbose_name="Sotuv ID")
    sale_date = models.DateTimeField(default=timezone.now, verbose_name="Sotuv sanasi")
    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPES, verbose_name="Mijoz turi")
    customer_name = models.CharField(
        max_length=255,
        help_text="Agar agent bo'lmasa, yakka mijoz ismi",
        blank=True,
        null=True,
        verbose_name="Mijoz ismi"
    )
    agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name="ticket_sales",
        blank=True,
        null=True,
        verbose_name="Agent"
    )
    seller = models.ForeignKey(
        Seller, on_delete=models.CASCADE, related_name="ticket_sales", verbose_name="Sotuvchi"
    )
    ticket_purchase = models.ForeignKey(
        TicketPurchase, on_delete=models.CASCADE, related_name="ticket_sales", verbose_name="Chipta xaridi"
    )
    quantity = models.PositiveIntegerField(verbose_name="Miqdori")
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Narxi")
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="UZS", verbose_name="Valyuta")
    notes = models.TextField(blank=True, null=True, verbose_name="Izohlar")

    # Calculated fields
    profit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Valyutalar bir xil bo'lmasa null bo'ladi",
        verbose_name="Foyda"
    )

    @property
    def total_price(self):
        return self.quantity * self.unit_price

    def save(self, *args, **kwargs):
        # Generate a sale ID if one doesn't exist
        if not self.sale_id:
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
        return f"Sotuv {self.sale_id} - {customer}"

    class Meta:
        ordering = ["-sale_date"]
        verbose_name = "Chipta sotuvi"
        verbose_name_plural = "Chipta sotuvlari"


class Payment(models.Model):
    """Records payments for ticket sales"""
    
    PAYMENT_TYPES = (
        ("full", "To'liq to'lov"),
        ("partial", "Qisman to'lov"),
    )
    
    payment_id = models.CharField(max_length=50, unique=True, editable=False, verbose_name="To'lov ID")
    payment_date = models.DateTimeField(default=timezone.now, verbose_name="To'lov sanasi")
    ticket_sale = models.ForeignKey(
        TicketSale, on_delete=models.CASCADE, related_name="payments", verbose_name="Chipta sotuvi"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Summa")
    currency = models.CharField(
        max_length=3, 
        choices=TicketSale.CURRENCY_CHOICES, 
        default="UZS",
        verbose_name="Valyuta"
    )
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.SET_NULL,
        related_name="payments",
        null=True,
        blank=True,
        verbose_name="To'lov usuli"
    )
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES, default="full", verbose_name="To'lov turi")
    notes = models.TextField(blank=True, null=True, verbose_name="Izohlar")
    
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
        return f"To'lov {self.payment_id} - {self.ticket_sale.sale_id} uchun"
    
    class Meta:
        ordering = ["-payment_date"]
        verbose_name = "To'lov"
        verbose_name_plural = "To'lovlar"
