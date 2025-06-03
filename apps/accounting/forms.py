from django import forms
from django.core.exceptions import ValidationError
from .models import Expenditure, FinancialAccount
from .validators import ExpenditureValidator, FinancialAccountValidator
from django.utils import timezone
from apps.core.constants import CurrencyChoices, AccountTypeChoices


class FinancialAccountForm(forms.ModelForm):
    name = forms.CharField(
        label="Hisob Nomi",
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': "Masalan: Asosiy Naqd Pul"})
    )
    account_type = forms.ChoiceField(
        label="Hisob Turi",
        choices=AccountTypeChoices.choices,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    currency = forms.ChoiceField(
        label="Valyuta",
        choices=CurrencyChoices.choices,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    current_balance = forms.DecimalField(
        label="Balans",
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '0.00', 'step': '0.01'}),
        min_value=0,
        initial=0.00,
        help_text="Hisobning dastlabki balansini kiriting"
    )
    account_details = forms.CharField(
        label="Hisob Ma'lumotlari",
        widget=forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 2, 'placeholder': "Qo'shimcha ma'lumotlar"}),
        required=False,
        help_text="Masalan: karta oxirgi 4 raqami, bank hisob raqami, va h.k."
    )

    class Meta:
        model = FinancialAccount
        fields = ['name', 'account_type', 'currency', 'current_balance', 'account_details']

    def __init__(self, *args, **kwargs):
        self.instance_exists = kwargs.get('instance') and kwargs['instance'].pk
        super().__init__(*args, **kwargs)
        
        # Make current_balance readonly if editing existing account (users should use transactions)
        if self.instance_exists:
            self.fields['current_balance'].widget.attrs['readonly'] = True
            self.fields['current_balance'].help_text = "Balansni to'lovlar va xarajatlar orqali o'zgartiring"

    def clean(self):
        """Use centralized validation"""
        cleaned_data = super().clean()
        
        name = cleaned_data.get('name')
        account_type = cleaned_data.get('account_type')
        currency = cleaned_data.get('currency')
        current_balance = cleaned_data.get('current_balance')
        account_details = cleaned_data.get('account_details')

        try:
            validated_data = FinancialAccountValidator.validate_financial_account(
                name=name,
                account_type=account_type,
                currency=currency,
                current_balance=current_balance,
                account_details=account_details,
                account_instance=self.instance
            )
            cleaned_data.update(validated_data)
        except ValidationError as e:
            if hasattr(e, 'message'):
                raise ValidationError(e.message)
            raise

        return cleaned_data


class ExpenditureForm(forms.ModelForm):
    expenditure_type = forms.ChoiceField(
        label="Xarajat Turi",
        choices=Expenditure.ExpenditureType.choices,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_expenditure_type'}),
        initial=Expenditure.ExpenditureType.GENERAL
    )
    expenditure_date = forms.DateTimeField(
        label="Xarajat Sanasi",
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control form-control-sm'}),
        initial=timezone.now
    )
    description = forms.CharField(
        label="Tavsifi",
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': "Xarajat tavsifi"})
    )
    amount = forms.DecimalField(
        label="Miqdori",
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '0.00'}),
        min_value=0.01
    )
    currency = forms.ChoiceField(
        label="Valyuta",
        choices=CurrencyChoices.choices,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_currency'})
    )
    paid_from_account = forms.ModelChoiceField(
        label="To'lov Hisobi",
        queryset=FinancialAccount.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_paid_from_account'}),
        help_text="Xarajat qaysi hisobdan to'lanishini tanlang."
    )
    supplier = forms.ModelChoiceField(
        label="Ta'minotchi",
        queryset=None,  # Will be set in __init__
        widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_supplier'}),
        required=False,
        help_text="Ta'minotchiga to'lov qilish uchun tanlang"
    )
    notes = forms.CharField(
        label="Qo'shimcha Izohlar",
        widget=forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
        required=False
    )

    class Meta:
        model = Expenditure
        fields = ['expenditure_type', 'expenditure_date', 'description', 'amount', 'currency', 'paid_from_account', 'supplier', 'notes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Import here to avoid circular imports
        from apps.contacts.models import Supplier
        
        self.fields['paid_from_account'].empty_label = "Hisobni tanlang"
        self.fields['supplier'].queryset = Supplier.objects.filter().order_by('name')
        self.fields['supplier'].empty_label = "Ta'minotchini tanlang"

    def clean(self):
        """Validate form data"""
        cleaned_data = super().clean()
        
        expenditure_type = cleaned_data.get('expenditure_type')
        supplier = cleaned_data.get('supplier')
        currency = cleaned_data.get('currency')
        paid_from_account = cleaned_data.get('paid_from_account')
        
        # Validate expenditure type and supplier relationship
        if expenditure_type == Expenditure.ExpenditureType.SUPPLIER_PAYMENT and not supplier:
            self.add_error('supplier', "Ta'minotchiga to'lov qilish uchun ta'minotchi tanlanishi kerak.")
        
        if supplier and expenditure_type != Expenditure.ExpenditureType.SUPPLIER_PAYMENT:
            self.add_error('expenditure_type', "Ta'minotchi tanlangan bo'lsa, xarajat turi 'Ta'minotchiga to'lov' bo'lishi kerak.")
        
        # Validate currency match with account
        if paid_from_account and currency and paid_from_account.currency != currency:
            self.add_error('paid_from_account', f"Valyuta mos kelmaydi: hisob {paid_from_account.currency} ishlatadi, xarajat {currency} ishlatadi.")

        return cleaned_data

    def save(self, commit=True):
        """Override save to handle validation errors gracefully"""
        try:
            expenditure = super().save(commit=False)
            
            # Set description for supplier payments
            if (expenditure.expenditure_type == Expenditure.ExpenditureType.SUPPLIER_PAYMENT and 
                expenditure.supplier and not expenditure.description):
                expenditure.description = f"Payment to {expenditure.supplier.name}"
            
            if commit:
                expenditure.save()
            return expenditure
        except ValidationError as e:
            # Convert model validation errors to form errors
            if hasattr(e, 'error_dict'):
                for field, errors in e.error_dict.items():
                    for error in errors:
                        self.add_error(field, error.message)
            else:
                self.add_error(None, str(e))
            return None


class SupplierPaymentForm(forms.ModelForm):
    """Simplified form specifically for supplier payments"""
    
    expenditure_date = forms.DateTimeField(
        label="To'lov Sanasi",
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control form-control-sm'}),
        initial=timezone.now
    )
    amount = forms.DecimalField(
        label="To'lov Miqdori",
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '0.00', 'step': '0.01'}),
        min_value=0.01
    )
    currency = forms.ChoiceField(
        label="Valyuta",
        choices=CurrencyChoices.choices,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    paid_from_account = forms.ModelChoiceField(
        label="To'lov Hisobi",
        queryset=FinancialAccount.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
        help_text="To'lov qaysi hisobdan amalga oshiriladi"
    )
    notes = forms.CharField(
        label="Izohlar",
        widget=forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
        required=False
    )

    class Meta:
        model = Expenditure
        fields = ['expenditure_date', 'amount', 'currency', 'paid_from_account', 'notes']

    def __init__(self, *args, **kwargs):
        self.supplier = kwargs.pop('supplier', None)
        super().__init__(*args, **kwargs)
        
        self.fields['paid_from_account'].empty_label = "Hisobni tanlang"
        
        # Filter accounts by currency if we have a currency preference
        if self.supplier:
            # Set default description
            self.initial['description'] = f"Payment to {self.supplier.name}"

    def clean(self):
        """Validate form data"""
        cleaned_data = super().clean()
        
        currency = cleaned_data.get('currency')
        paid_from_account = cleaned_data.get('paid_from_account')
        
        # Validate currency match with account
        if paid_from_account and currency and paid_from_account.currency != currency:
            self.add_error('paid_from_account', f"Valyuta mos kelmaydi: hisob {paid_from_account.currency} ishlatadi, to'lov {currency} ishlatadi.")

        return cleaned_data

    def save(self, commit=True):
        """Save supplier payment"""
        expenditure = super().save(commit=False)
        
        # Set expenditure type and supplier
        expenditure.expenditure_type = Expenditure.ExpenditureType.SUPPLIER_PAYMENT
        expenditure.supplier = self.supplier
        expenditure.description = f"Payment to {self.supplier.name}"
        
        if commit:
            expenditure.save()
        return expenditure 