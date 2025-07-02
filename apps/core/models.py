from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class Salesperson(models.Model):
    """Sales representative model extending Django User"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='salesperson_profile')
    phone_number = models.CharField(max_length=20, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}"

    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username

    class Meta:
        verbose_name = "Sotuvchi"
        verbose_name_plural = "Sotuvchilar"
        ordering = ['user__first_name', 'user__last_name']


