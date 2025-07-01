from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import Salesperson

class LoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-lg",
                "placeholder": "Foydalanuvchi nomi",
            }
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control form-control-lg",
                "placeholder": "Parol",
            }
        )
    )


class SalespersonForm(forms.Form):
    # User fields
    username = forms.CharField(
        max_length=150,
        label="Foydalanuvchi nomi",
        help_text="Tizimga kirish uchun foydalanuvchi nomi",
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm'})
    )
    first_name = forms.CharField(
        max_length=30,
        label="Ism",
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm'})
    )
    last_name = forms.CharField(
        max_length=30,
        label="Familiya", 
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm'})
    )
    email = forms.EmailField(
        required=False,
        label="Email manzil",
        widget=forms.EmailInput(attrs={'class': 'form-control form-control-sm'})
    )
    password = forms.CharField(
        min_length=6,
        label="Parol",
        help_text="Kamida 6 ta belgi",
        widget=forms.PasswordInput(attrs={'class': 'form-control form-control-sm'})
    )
    password_confirm = forms.CharField(
        min_length=6,
        label="Parolni tasdiqlash",
        widget=forms.PasswordInput(attrs={'class': 'form-control form-control-sm'})
    )
    
    # Salesperson fields
    phone_number = forms.CharField(
        max_length=20,
        required=False,
        label="Telefon raqami",
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm'})
    )
    is_active = forms.BooleanField(
        required=False,
        initial=True,
        label="Faol",
        help_text="Sotuvchi faol holatda bo'lsin",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise ValidationError("Bu foydalanuvchi nomi allaqachon mavjud.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise ValidationError("Bu email manzil allaqachon mavjud.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        if password and password_confirm:
            if password != password_confirm:
                raise ValidationError("Parollar mos kelmaydi.")
        
        return cleaned_data

    def save(self):
        """Create both User and Salesperson in one transaction"""
        try:
            with transaction.atomic():
                # Create user
                user = User.objects.create_user(
                    username=self.cleaned_data['username'],
                    first_name=self.cleaned_data['first_name'],
                    last_name=self.cleaned_data['last_name'],
                    email=self.cleaned_data.get('email', ''),
                    password=self.cleaned_data['password']
                )
                
                # Create salesperson
                salesperson = Salesperson.objects.create(
                    user=user,
                    phone_number=self.cleaned_data.get('phone_number', ''),
                    is_active=self.cleaned_data.get('is_active', True)
                )
                
                return salesperson
                
        except Exception as e:
            raise ValidationError(f"Sotuvchini yaratishda xatolik: {e}") 