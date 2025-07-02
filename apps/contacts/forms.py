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

class BasePaymentForm(forms.ModelForm):
    class Meta:
        abstract = True
        fields = ['payment_date', 'amount', 'currency', 'notes']
        labels = {
            'payment_date': "To'lov Sanasi",
            'amount': "To'lov Miqdori",
            'currency': "Valyuta",
            'notes': "Izohlar",
        }
        widgets = {
            'payment_date': forms.DateTimeInput(attrs={'class': 'form-control form-control-sm', 'type': 'datetime-local'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01', 'placeholder': '0.00'}),
            'currency': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'notes': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_account_field()
    
    def setup_account_field(self):
        account_field_name = self.get_account_field_name()
        if account_field_name in self.fields:
            self.fields[account_field_name].queryset = FinancialAccount.objects.filter(
                is_active=True
            ).order_by('currency', 'name')
    
    def get_account_field_name(self):
        raise NotImplementedError("Subclasses must implement get_account_field_name")
    
    def clean(self):
        cleaned_data = super().clean()
        currency = cleaned_data.get('currency')
        account_field_name = self.get_account_field_name()
        account = cleaned_data.get(account_field_name)
        
        if currency and account and account.currency != currency:
            raise forms.ValidationError(
                f"Hisob valyutasi ({account.currency}) "
                f"to'lov valyutasi ({currency}) bilan mos kelmaydi."
            )
        
        return cleaned_data

class AgentPaymentForm(BasePaymentForm):
    class Meta(BasePaymentForm.Meta):
        model = AgentPayment
        fields = BasePaymentForm.Meta.fields + ['paid_to_account']
        labels = dict(BasePaymentForm.Meta.labels, paid_to_account="To'lov Hisobi")
        widgets = dict(BasePaymentForm.Meta.widgets, 
                      paid_to_account=forms.Select(attrs={'class': 'form-select form-select-sm'}))

    def get_account_field_name(self):
        return 'paid_to_account'

class SupplierPaymentForm(BasePaymentForm):
    class Meta(BasePaymentForm.Meta):
        model = SupplierPayment
        fields = BasePaymentForm.Meta.fields + ['paid_from_account']
        labels = dict(BasePaymentForm.Meta.labels, paid_from_account="To'lov Hisobi")
        widgets = dict(BasePaymentForm.Meta.widgets,
                      paid_from_account=forms.Select(attrs={'class': 'form-select form-select-sm'}))

    def get_account_field_name(self):
        return 'paid_from_account'