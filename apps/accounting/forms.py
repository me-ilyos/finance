from django import forms
from .models import Expenditure, FinancialAccount
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['paid_from_account'].empty_label = "Hisobni tanlang"