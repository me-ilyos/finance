from django.db import models

# Create your models here.

class Supplier(models.Model):
    name = models.CharField(max_length=255, unique=True)
    phone_number = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Agent(models.Model):
    name = models.CharField(max_length=255, unique=True)
    phone_number = models.CharField(max_length=50, blank=True, null=True)
    outstanding_balance_uzs = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    outstanding_balance_usd = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
