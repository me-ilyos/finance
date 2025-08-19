from django import forms
from django.core.exceptions import ValidationError
from .models import Expenditure, FinancialAccount, Transfer, Deposit
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
        
        if self.instance_exists:
            self.fields['current_balance'].widget.attrs['readonly'] = True
            self.fields['current_balance'].help_text = "Balansni to'lovlar va xarajatlar orqali o'zgartiring"


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
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '0.00'})
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
    notes = forms.CharField(
        label="Qo'shimcha Izohlar",
        widget=forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
        required=False
    )

    class Meta:
        model = Expenditure
        fields = ['expenditure_date', 'description', 'amount', 'currency', 'paid_from_account', 'notes']
        widgets = {
            'expenditure_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Xarajat tavsifi'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'currency': forms.Select(attrs={'class': 'form-select'}),
            'paid_from_account': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Qo\'shimcha izoh (ixtiyoriy)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show active accounts
        self.fields['paid_from_account'].queryset = FinancialAccount.objects.filter(is_active=True)
        
        # Set labels in Uzbek
        self.fields['expenditure_date'].label = "Xarajat sanasi"
        self.fields['description'].label = "Tavsif"
        self.fields['amount'].label = "Summa"
        self.fields['currency'].label = "Valyuta"
        self.fields['paid_from_account'].label = "To'lov hisobi"
        self.fields['notes'].label = "Izoh"

    def clean(self):
        cleaned_data = super().clean()
        paid_from_account = cleaned_data.get('paid_from_account')
        currency = cleaned_data.get('currency')
        
        # Check if the account currency matches the expenditure currency
        if paid_from_account and currency and paid_from_account.currency != currency:
            raise ValidationError(
                f"Hisob valyutasi ({paid_from_account.currency}) va xarajat valyutasi ({currency}) mos kelmaydi."
            )
        
        return cleaned_data


class TransferForm(forms.ModelForm):
    class Meta:
        model = Transfer
        fields = ['transfer_date', 'from_account', 'to_account', 'amount', 'conversion_rate', 'description', 'notes']
        widgets = {
            'transfer_date': forms.DateTimeInput(attrs={'type': 'hidden'}),
            'from_account': forms.Select(attrs={'class': 'form-select'}),
            'to_account': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'conversion_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001', 'min': '0.0001'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Izoh (ixtiyoriy)'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Batafsil izoh (ixtiyoriy)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show active accounts
        active_accounts = FinancialAccount.objects.filter(is_active=True)
        self.fields['from_account'].queryset = active_accounts
        self.fields['to_account'].queryset = active_accounts
        
        # Set initial transfer_date to current datetime
        if not self.instance.pk:
            self.fields['transfer_date'].initial = timezone.now()
        
        # Set default values
        self.fields['description'].initial = 'Transfer'
        self.fields['notes'].initial = ''
        
        # Make conversion rate and optional fields not required
        self.fields['conversion_rate'].required = False
        self.fields['description'].required = False
        self.fields['notes'].required = False

    def clean(self):
        cleaned_data = super().clean()
        from_account = cleaned_data.get('from_account')
        to_account = cleaned_data.get('to_account')
        amount = cleaned_data.get('amount')
        conversion_rate = cleaned_data.get('conversion_rate')
        
        # Set default description if not provided
        if not cleaned_data.get('description'):
            cleaned_data['description'] = 'Transfer'
        
        # Check if accounts are different
        if from_account and to_account and from_account == to_account:
            raise ValidationError("Bir xil hisobga transfer qilish mumkin emas")
        
        # Check sufficient balance
        if from_account and amount:
            if not from_account.has_sufficient_balance(amount):
                raise ValidationError(
                    f"Hisobda yetarli mablag' yo'q. "
                    f"Mavjud: {from_account.current_balance:,.2f} {from_account.currency}"
                )
        
        # Check currency conversion requirements
        if from_account and to_account:
            if from_account.currency != to_account.currency:
                if not conversion_rate:
                    raise ValidationError("Turli valyutalar uchun konversiya kursi talab qilinadi")
                if conversion_rate <= 0:
                    raise ValidationError("Konversiya kursi musbat bo'lishi kerak")
        
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Set currency from from_account
        if self.cleaned_data.get('from_account'):
            instance.currency = self.cleaned_data['from_account'].currency
        
        # Ensure description has a value
        if not instance.description:
            instance.description = 'Transfer'
            
        if commit:
            instance.save()
        return instance


class DepositForm(forms.ModelForm):
    class Meta:
        model = Deposit
        fields = ['deposit_date', 'to_account', 'amount', 'currency', 'description', 'notes']
        widgets = {
            'deposit_date': forms.DateTimeInput(attrs={'type': 'hidden'}),
            'to_account': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'currency': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Izoh (ixtiyoriy)'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Batafsil izoh (ixtiyoriy)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['to_account'].queryset = FinancialAccount.objects.filter(is_active=True)
        if not self.instance.pk:
            self.fields['deposit_date'].initial = timezone.now()
        self.fields['description'].initial = 'Deposit'
        self.fields['notes'].initial = ''
        self.fields['description'].required = False
        self.fields['notes'].required = False
