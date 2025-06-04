from django import forms
from .models import Agent, Supplier, AgentPayment, SupplierPayment
from apps.accounting.models import FinancialAccount

class AgentForm(forms.ModelForm):
    class Meta:
        model = Agent
        fields = ['name', 'phone_number', 'notes', 'balance_uzs', 'balance_usd']
        labels = {
            'name': "Nomi",
            'phone_number': "Telefon Raqami",
            'notes': "Izohlar",
            'balance_uzs': "Boshlang'ich Balans UZS",
            'balance_usd': "Boshlang'ich Balans USD",
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'notes': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
            'balance_uzs': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm', 
                'step': '0.01',
                'placeholder': '0.00'
            }),
            'balance_usd': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm', 
                'step': '0.01',
                'placeholder': '0.00'
            }),
        }
        help_texts = {
            'balance_uzs': "Musbat: Agent qarzdor | Manfiy: Siz qarzdorsiz",
            'balance_usd': "Musbat: Agent qarzdor | Manfiy: Siz qarzdorsiz",
        }

class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'phone_number', 'notes', 'balance_uzs', 'balance_usd']
        labels = {
            'name': "Nomi",
            'phone_number': "Telefon Raqami",
            'notes': "Izohlar",
            'balance_uzs': "Boshlang'ich Balans UZS",
            'balance_usd': "Boshlang'ich Balans USD",
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'notes': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
            'balance_uzs': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm', 
                'step': '0.01',
                'placeholder': '0.00'
            }),
            'balance_usd': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm', 
                'step': '0.01',
                'placeholder': '0.00'
            }),
        }
        help_texts = {
            'balance_uzs': "Musbat: Siz qarzdorsiz | Manfiy: Ta'minotchi qarzdor",
            'balance_usd': "Musbat: Siz qarzdorsiz | Manfiy: Ta'minotchi qarzdor",
        }

class AgentPaymentForm(forms.ModelForm):
    class Meta:
        model = AgentPayment
        fields = ['payment_date', 'amount', 'currency', 'paid_to_account', 'notes']
        labels = {
            'payment_date': "To'lov Sanasi",
            'amount': "To'lov Miqdori",
            'currency': "Valyuta",
            'paid_to_account': "To'lov Hisobi",
            'notes': "Izohlar",
        }
        widgets = {
            'payment_date': forms.DateTimeInput(attrs={'class': 'form-control form-control-sm', 'type': 'datetime-local'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01', 'placeholder': '0.00'}),
            'currency': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'paid_to_account': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'notes': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Setup account queryset - filter by currency if currency is selected
        self.fields['paid_to_account'].queryset = FinancialAccount.objects.filter(
            is_active=True
        ).order_by('currency', 'name')
    
    def clean(self):
        cleaned_data = super().clean()
        currency = cleaned_data.get('currency')
        paid_to_account = cleaned_data.get('paid_to_account')
        
        # Validate currency match with account
        if currency and paid_to_account and paid_to_account.currency != currency:
            raise forms.ValidationError(
                f"Hisob valyutasi ({paid_to_account.currency}) "
                f"to'lov valyutasi ({currency}) bilan mos kelmaydi."
            )
        
        return cleaned_data


class SupplierPaymentForm(forms.ModelForm):
    class Meta:
        model = SupplierPayment
        fields = ['payment_date', 'amount', 'currency', 'paid_from_account', 'notes']
        labels = {
            'payment_date': "To'lov Sanasi",
            'amount': "To'lov Miqdori",
            'currency': "Valyuta",
            'paid_from_account': "To'lov Hisobi",
            'notes': "Izohlar",
        }
        widgets = {
            'payment_date': forms.DateTimeInput(attrs={'class': 'form-control form-control-sm', 'type': 'datetime-local'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01', 'placeholder': '0.00'}),
            'currency': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'paid_from_account': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'notes': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Setup account queryset - filter by currency if currency is selected
        self.fields['paid_from_account'].queryset = FinancialAccount.objects.filter(
            is_active=True
        ).order_by('currency', 'name')
    
    def clean(self):
        cleaned_data = super().clean()
        currency = cleaned_data.get('currency')
        paid_from_account = cleaned_data.get('paid_from_account')
        
        # Validate currency match with account
        if currency and paid_from_account and paid_from_account.currency != currency:
            raise forms.ValidationError(
                f"Hisob valyutasi ({paid_from_account.currency}) "
                f"to'lov valyutasi ({currency}) bilan mos kelmaydi."
            )
        
        return cleaned_data