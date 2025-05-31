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
        fields = ['name', 'phone_number', 'notes']
        labels = {
            'name': "Nomi",
            'phone_number': "Telefon Raqami",
            'notes': "Izohlar",
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'notes': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
        }

class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'phone_number', 'notes']
        labels = {
            'name': "Nomi",
            'phone_number': "Telefon Raqami",
            'notes': "Izohlar",
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'notes': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
        }

class AgentPaymentForm(forms.ModelForm):
    related_sale = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        label="To'lov qilinayotgan Sotuv (Qarz)",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
        help_text="Agar bu to'lov ma'lum bir sotuv uchun bo'lsa, uni tanlang."
    )

    class Meta:
        model = AgentPayment
        fields = ['payment_date', 'related_sale', 'amount_paid_uzs', 'amount_paid_usd', 'paid_to_account', 'notes']
        widgets = {
            'payment_date': forms.DateTimeInput(attrs={'class': 'form-control form-control-sm', 'type': 'datetime-local'}),
            'amount_paid_uzs': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01'}),
            'amount_paid_usd': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01'}),
            'paid_to_account': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'notes': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        agent = kwargs.pop('agent', None)
        super().__init__(*args, **kwargs)
        
        if agent:
            self.instance.agent = agent
            self._setup_related_sale_queryset(agent)

        self._setup_account_queryset()

    def _setup_related_sale_queryset(self, agent):
        """Setup queryset for related sales"""
        from django.apps import apps
        Sale = apps.get_model('sales', 'Sale')
        
        self.fields['related_sale'].queryset = Sale.objects.filter(
            agent=agent,
            total_sale_amount__gt=models.F('paid_amount_on_this_sale') 
        ).select_related('related_acquisition__ticket').order_by('-sale_date')
        
        self.fields['related_sale'].label_from_instance = self._format_sale_label

    def _setup_account_queryset(self):
        """Setup queryset for payment accounts"""
        self.fields['paid_to_account'].queryset = FinancialAccount.objects.filter(
            is_active=True, 
            currency__in=[CurrencyChoices.UZS, CurrencyChoices.USD]
        ).order_by('currency', 'name')

    def _format_sale_label(self, obj):
        """Format sale label for display"""
        return f"Sotuv {obj.id} ({obj.sale_date.strftime('%d-%m-%Y')}) - Balans: {obj.balance_due_on_this_sale} {obj.sale_currency}"

    def clean(self):
        """Validate form data using centralized validator"""
        cleaned_data = super().clean()
        
        # Get values with defaults
        amount_uzs = cleaned_data.get('amount_paid_uzs') or Decimal('0.00')
        amount_usd = cleaned_data.get('amount_paid_usd') or Decimal('0.00')
        paid_to_account = cleaned_data.get('paid_to_account')
        related_sale = cleaned_data.get('related_sale')
        
        # Use centralized validation
        try:
            PaymentValidator.validate_agent_payment(
                agent=self.instance.agent,
                amount_uzs=amount_uzs,
                amount_usd=amount_usd,
                paid_to_account=paid_to_account,
                related_sale=related_sale,
                payment_instance=self.instance
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