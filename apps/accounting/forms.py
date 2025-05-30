from django import forms
from .models import Expenditure, FinancialAccount
from django.utils import timezone

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
        choices=Expenditure.Currency.choices,
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
        cleaned_data = super().clean()
        paid_from_account = cleaned_data.get('paid_from_account')
        currency = cleaned_data.get('currency')
        amount = cleaned_data.get('amount')

        if paid_from_account and currency:
            if paid_from_account.currency != currency:
                self.add_error('paid_from_account', 
                               f"Tanlangan hisob valyutasi ({paid_from_account.currency}) "
                               f"xarajat valyutasi ({currency}) bilan mos kelmadi.")
        
        if amount is not None and amount <= 0:
            self.add_error('amount', "Xarajat miqdori musbat son bo'lishi kerak.")

        return cleaned_data 