from django import forms
from django.db import models
from .models import Agent, Supplier, AgentPayment
from apps.accounting.models import FinancialAccount
from apps.core.constants import CurrencyChoices
from .validators import PaymentValidator
from decimal import Decimal

class AgentForm(forms.ModelForm):
    class Meta:
        model = Agent
        fields = ['name', 'phone_number', 'notes', 'outstanding_balance_uzs', 'outstanding_balance_usd']
        labels = {
            'name': "Nomi",
            'phone_number': "Telefon Raqami",
            'notes': "Izohlar",
            'outstanding_balance_uzs': "Balans UZS",
            'outstanding_balance_usd': "Balans USD",
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'notes': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
            'outstanding_balance_uzs': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm', 
                'step': '0.01',
                'placeholder': '0.00'
            }),
            'outstanding_balance_usd': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm', 
                'step': '0.01',
                'placeholder': '0.00'
            }),
        }
        help_texts = {
            'outstanding_balance_uzs': "Musbat: Agent sizga qarzdor | Manfiy: Siz agentga qarzdorsiz",
            'outstanding_balance_usd': "Musbat: Agent sizga qarzdor | Manfiy: Siz agentga qarzdorsiz",
        }

class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'phone_number', 'notes', 'current_balance_uzs', 'current_balance_usd']
        labels = {
            'name': "Nomi",
            'phone_number': "Telefon Raqami",
            'notes': "Izohlar",
            'current_balance_uzs': "Joriy Balans UZS",
            'current_balance_usd': "Joriy Balans USD",
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'notes': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
            'current_balance_uzs': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm', 
                'step': '0.01',
                'placeholder': '0.00'
            }),
            'current_balance_usd': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm', 
                'step': '0.01',
                'placeholder': '0.00'
            }),
        }
        help_texts = {
            'current_balance_uzs': "Exceldan ko'chirishda joriy balansni kiriting (musbat, manfiy yoki nol)",
            'current_balance_usd': "Exceldan ko'chirishda joriy balansni kiriting (musbat, manfiy yoki nol)",
        }

class AgentPaymentForm(forms.ModelForm):
    class Meta:
        model = AgentPayment
        fields = ['payment_date', 'amount_paid_uzs', 'amount_paid_usd', 'paid_to_account', 'notes']
        labels = {
            'payment_date': "To'lov Sanasi",
            'amount_paid_uzs': "To'lov Miqdori (UZS)",
            'amount_paid_usd': "To'lov Miqdori (USD)",
            'paid_to_account': "To'lov Hisobi",
            'notes': "Izohlar",
        }
        widgets = {
            'payment_date': forms.DateTimeInput(attrs={'class': 'form-control form-control-sm', 'type': 'datetime-local'}),
            'amount_paid_uzs': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01', 'placeholder': '0.00'}),
            'amount_paid_usd': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01', 'placeholder': '0.00'}),
            'paid_to_account': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'notes': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
        }
        help_texts = {
            'amount_paid_uzs': "Faqat UZS yoki USD da to'lov qiling, ikkalasini ham emas",
            'amount_paid_usd': "Faqat UZS yoki USD da to'lov qiling, ikkalasini ham emas",
        }

    def __init__(self, *args, **kwargs):
        agent = kwargs.pop('agent', None)
        super().__init__(*args, **kwargs)
        
        if agent:
            self.instance.agent = agent

        self._setup_account_queryset()

    def _setup_account_queryset(self):
        """Setup queryset for payment accounts"""
        self.fields['paid_to_account'].queryset = FinancialAccount.objects.filter(
            is_active=True, 
            currency__in=[CurrencyChoices.UZS, CurrencyChoices.USD]
        ).order_by('currency', 'name')

    def clean(self):
        """Validate form data using centralized validator"""
        cleaned_data = super().clean()
        
        # Get values with defaults
        amount_uzs = cleaned_data.get('amount_paid_uzs') or Decimal('0.00')
        amount_usd = cleaned_data.get('amount_paid_usd') or Decimal('0.00')
        paid_to_account = cleaned_data.get('paid_to_account')
        
        # Use centralized validation
        try:
            PaymentValidator.validate_agent_payment(
                agent=self.instance.agent,
                amount_uzs=amount_uzs,
                amount_usd=amount_usd,
                paid_to_account=paid_to_account
            )
        except forms.ValidationError as e:
            # Add errors to form
            if hasattr(e, 'error_dict'):
                for field, errors in e.error_dict.items():
                    for error in errors:
                        self.add_error(field, error.message)
            else:
                self.add_error(None, str(e))

        return cleaned_data 