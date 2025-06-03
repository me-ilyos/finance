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
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    paid_from_account = forms.ModelChoiceField(
        label="To'lov Hisobi",
        queryset=FinancialAccount.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
        help_text="Xarajat qaysi hisobdan to'lanishini tanlang."
    )
    notes = forms.CharField(
        label="Qo'shimcha Izohlar",
        widget=forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
        required=False
    )

    class Meta:
        model = Expenditure
        fields = ['expenditure_date', 'description', 'amount', 'currency', 'paid_from_account', 'notes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['paid_from_account'].empty_label = "Hisobni tanlang"

    def clean(self):
        """Use centralized validation"""
        cleaned_data = super().clean()
        
        expenditure_date = cleaned_data.get('expenditure_date')
        description = cleaned_data.get('description')
        amount = cleaned_data.get('amount')
        currency = cleaned_data.get('currency')
        paid_from_account = cleaned_data.get('paid_from_account')

        try:
            validated_data = ExpenditureValidator.validate_expenditure(
                expenditure_date=expenditure_date,
                description=description,
                amount=amount,
                currency=currency,
                paid_from_account=paid_from_account,
                expenditure_instance=self.instance
            )
            cleaned_data.update(validated_data)
        except ValidationError as e:
            if hasattr(e, 'message'):
                raise ValidationError(e.message)
            raise

        return cleaned_data

    def save(self, commit=True):
        """Override save to handle validation errors gracefully"""
        try:
            return super().save(commit=commit)
        except ValidationError as e:
            # Convert model validation errors to form errors
            if hasattr(e, 'error_dict'):
                for field, errors in e.error_dict.items():
                    for error in errors:
                        self.add_error(field, error.message)
            else:
                self.add_error(None, str(e))
            return None 