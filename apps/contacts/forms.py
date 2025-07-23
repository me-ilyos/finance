from django import forms
from .models import Agent, Supplier, AgentPayment, SupplierPayment, Commission
from apps.accounting.models import FinancialAccount
from django.utils import timezone


class AcquisitionChoiceField(forms.ModelChoiceField):
    """Custom choice field for acquisitions with better display"""
    def label_from_instance(self, obj):
        return obj.get_commission_display()


class BaseContactForm(forms.ModelForm):
    class Meta:
        abstract = True
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

    def clean_balance_uzs(self):
        value = self.cleaned_data.get('balance_uzs')
        if value is None:
            return 0
        return value

    def clean_balance_usd(self):
        value = self.cleaned_data.get('balance_usd')
        if value is None:
            return 0
        return value


class SupplierForm(BaseContactForm):
    class Meta(BaseContactForm.Meta):
        model = Supplier
        help_texts = {
            'balance_uzs': "Musbat: Siz qarzdorsiz | Manfiy: Ta'minotchi qarzdor",
            'balance_usd': "Musbat: Siz qarzdorsiz | Manfiy: Ta'minotchi qarzdor",
        }


class CommissionForm(forms.ModelForm):
    acquisition = AcquisitionChoiceField(
        queryset=None,
        empty_label="Xaridni tanlang...",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
        label="Xarid"
    )
    
    class Meta:
        model = Commission
        fields = ['acquisition', 'commission_date', 'amount', 'notes']
        labels = {
            'acquisition': "Xarid",
            'commission_date': "Komissiya Sanasi",
            'amount': "Komissiya Miqdori",
            'notes': "Izohlar",
        }
        widgets = {
            'commission_date': forms.DateTimeInput(attrs={'class': 'form-control form-control-sm', 'type': 'datetime-local'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01', 'placeholder': '0.00'}),
            'notes': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        supplier = kwargs.pop('supplier', None)
        super().__init__(*args, **kwargs)
        
        if supplier:
            # Only show acquisitions for this specific supplier that don't have commissions yet
            self.fields['acquisition'].queryset = supplier.acquisitions.filter(
                is_active=True,
                commissions__isnull=True  # Exclude acquisitions that already have commissions
            ).select_related('ticket').order_by('-acquisition_date')
        else:
            self.fields['acquisition'].queryset = self.fields['acquisition'].queryset.none()
            
        # Set current datetime as default
        current_time = timezone.now().strftime('%Y-%m-%dT%H:%M')
        self.fields['commission_date'].initial = current_time

    def clean(self):
        cleaned_data = super().clean()
        acquisition = cleaned_data.get('acquisition')
        
        if acquisition:
            # Automatically set currency to match acquisition currency
            cleaned_data['currency'] = acquisition.currency
            # Set supplier to match acquisition supplier
            cleaned_data['supplier'] = acquisition.supplier
        
        return cleaned_data


class AgentForm(BaseContactForm):
    class Meta(BaseContactForm.Meta):
        model = Agent
        help_texts = {
            'balance_uzs': "Musbat: Agent qarzdor | Manfiy: Siz qarzdorsiz",
            'balance_usd': "Musbat: Agent qarzdor | Manfiy: Siz qarzdorsiz",
        }


class AgentPaymentForm(forms.ModelForm):
    PAYMENT_TYPE_CHOICES = [
        ('same_currency', 'Oddiy to\'lov (bir xil valyuta)'),
        ('cross_currency', 'Valyuta konvertatsiyasi bilan to\'lov'),
    ]
    
    CONVERSION_DIRECTION_CHOICES = [
        ('usd_to_uzs', 'USD → UZS (Agent USD olib keldi, UZS qarzni to\'laydi)'),
        ('uzs_to_usd', 'UZS → USD (Agent UZS olib keldi, USD qarzni to\'laydi)'),
    ]
    
    payment_type = forms.ChoiceField(
        choices=PAYMENT_TYPE_CHOICES,
        label="To'lov turi",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_payment_type'}),
        initial='same_currency'
    )
    
    conversion_direction = forms.ChoiceField(
        choices=CONVERSION_DIRECTION_CHOICES,
        label="Konvertatsiya yo'nalishi",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_conversion_direction'}),
        required=False,
        initial='usd_to_uzs'
    )
    
    exchange_rate = forms.DecimalField(
        label="Kurs (1 USD = ? UZS)",
        max_digits=10,
        decimal_places=4,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-sm', 
            'step': '0.0001', 
            'placeholder': '12500.0000',
            'id': 'id_exchange_rate'
        }),
        help_text="1 USD uchun necha UZS"
    )
    
    original_amount = forms.DecimalField(
        label="Olib kelgan miqdor",
        max_digits=20,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-sm', 
            'step': '0.01', 
            'placeholder': '0.00',
            'id': 'id_original_amount'
        }),
        help_text="Agent olib kelgan miqdor"
    )

    class Meta:
        model = AgentPayment
        fields = ['payment_date', 'payment_type', 'conversion_direction', 'amount', 'currency', 'exchange_rate', 'original_amount', 'paid_to_account', 'notes']
        labels = {
            'payment_date': "To'lov Sanasi",
            'amount': "To'lov Miqdori",
            'currency': "Valyuta",
            'paid_to_account': "To'lov Hisobi",
            'notes': "Izohlar",
        }
        widgets = {
            'payment_date': forms.DateTimeInput(attrs={'class': 'form-control form-control-sm', 'type': 'datetime-local'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01', 'placeholder': '0.00', 'id': 'id_amount'}),
            'currency': forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_currency'}),
            'paid_to_account': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'notes': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['paid_to_account'].queryset = FinancialAccount.objects.filter(
            is_active=True
        ).order_by('currency', 'name')
        
        # Set initial currency to UZS
        self.fields['currency'].initial = 'UZS'
        
        # Make currency and amount not required initially (will be set in clean method for cross-currency)
        self.fields['currency'].required = False
        self.fields['amount'].required = False
        
        # Add help text for account selection
        self.fields['paid_to_account'].help_text = "Valyuta konvertatsiyasi bo'lganda: Agent olib kelgan valyuta hisobini tanlang"

    def clean(self):
        cleaned_data = super().clean()
        payment_type = cleaned_data.get('payment_type')
        
        if payment_type == 'same_currency':
            # For same currency, ensure required fields are present
            if not cleaned_data.get('amount'):
                raise forms.ValidationError("To'lov miqdori kiritilishi kerak.")
            if not cleaned_data.get('currency'):
                raise forms.ValidationError("Valyuta tanlanishi kerak.")
        else:
            # Cross-currency validation
            conversion_direction = cleaned_data.get('conversion_direction')
            exchange_rate = cleaned_data.get('exchange_rate')
            original_amount = cleaned_data.get('original_amount')
            paid_to_account = cleaned_data.get('paid_to_account')
            
            if not all([conversion_direction, exchange_rate, original_amount]):
                raise forms.ValidationError("Valyuta konvertatsiyasi uchun barcha maydonlar to'ldirilishi kerak.")
            
            if exchange_rate <= 0:
                raise forms.ValidationError("Kurs musbat bo'lishi kerak.")
            
            if original_amount <= 0:
                raise forms.ValidationError("Olib kelgan miqdor musbat bo'lishi kerak.")
            
            # Calculate based on conversion direction
            if conversion_direction == 'usd_to_uzs':
                # Agent brings USD, pays UZS debt: USD × rate = UZS
                calculated_amount = original_amount * exchange_rate
                # Round to 2 decimal places to avoid precision issues
                calculated_amount = round(calculated_amount, 2)
                cleaned_data['amount'] = calculated_amount
                cleaned_data['currency'] = 'UZS'
                cleaned_data['original_currency'] = 'USD'
                expected_account_currency = 'USD'
            else:  # uzs_to_usd
                # Agent brings UZS, pays USD debt: UZS ÷ rate = USD
                calculated_amount = original_amount / exchange_rate
                # Round to 2 decimal places to avoid precision issues
                calculated_amount = round(calculated_amount, 2)
                cleaned_data['amount'] = calculated_amount
                cleaned_data['currency'] = 'USD'
                cleaned_data['original_currency'] = 'UZS'
                expected_account_currency = 'UZS'
            
            # Validate that account currency matches the original currency
            if paid_to_account and paid_to_account.currency != expected_account_currency:
                raise forms.ValidationError(
                    f"Tanlangan hisob {expected_account_currency} valyutasida bo'lishi kerak, "
                    f"chunki agent {expected_account_currency} olib keldi."
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
        self.fields['paid_from_account'].queryset = FinancialAccount.objects.filter(
            is_active=True
        ).order_by('currency', 'name')