from django import forms
from django.db import models
from .models import Agent, Supplier, AgentPayment
from apps.accounting.models import FinancialAccount
from apps.sales.models import Sale
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
        queryset=Sale.objects.none(),
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
            self.fields['related_sale'].queryset = Sale.objects.filter(
                agent=agent,
                total_sale_amount__gt=models.F('paid_amount_on_this_sale') 
            ).select_related('related_acquisition__ticket').order_by('-sale_date')
            self.fields['related_sale'].label_from_instance = lambda obj: f"Sotuv {obj.id} ({obj.sale_date.strftime('%d-%m-%Y')}) - Balans: {obj.balance_due_on_this_sale} {obj.sale_currency}"

        self.fields['paid_to_account'].queryset = FinancialAccount.objects.filter(
            is_active=True, currency__in=[FinancialAccount.Currency.UZS, FinancialAccount.Currency.USD]
        ).order_by('currency', 'name')

    def clean(self):
        cleaned_data = super().clean()
        amount_uzs = cleaned_data.get('amount_paid_uzs') or Decimal('0.00')
        amount_usd = cleaned_data.get('amount_paid_usd') or Decimal('0.00')
        paid_to_account = cleaned_data.get('paid_to_account')
        related_sale = cleaned_data.get('related_sale')

        if amount_uzs <= 0 and amount_usd <= 0:
            self.add_error(None, "To'lov miqdori noldan katta bo'lishi kerak.")

        payment_currency = None
        payment_amount = Decimal('0.00')
        if amount_uzs > 0 and amount_usd > 0:
            self.add_error(None, "Bir vaqtda UZS va USD da to'lov qilish mumkin emas. Iltimos alohida to'lov kiriting.")
        elif amount_uzs > 0:
            payment_currency = 'UZS'
            payment_amount = amount_uzs
        elif amount_usd > 0:
            payment_currency = 'USD'
            payment_amount = amount_usd
        
        if related_sale:
            if payment_currency and related_sale.sale_currency != payment_currency:
                self.add_error(None, f"To'lov valyutasi ({payment_currency}) tanlangan sotuv valyutasiga ({related_sale.sale_currency}) mos kelishi kerak.")
            
            if payment_currency == related_sale.sale_currency:
                if payment_amount > related_sale.balance_due_on_this_sale:
                    self.add_error(
                        'amount_paid_uzs' if payment_currency == 'UZS' else 'amount_paid_usd',
                        f"To'lov miqdori ({payment_amount} {payment_currency}) tanlangan sotuv qoldig'idan ({related_sale.balance_due_on_this_sale} {related_sale.sale_currency}) oshmasligi kerak."
                    )
            elif not payment_currency and (amount_uzs > 0 or amount_usd > 0):
                 self.add_error(None, "To'lov valyutasini aniqlashda xatolik.")

        if paid_to_account and payment_currency:
            if paid_to_account.currency != payment_currency:
                self.add_error('paid_to_account', f"Hisob raqam valyutasi ({paid_to_account.currency}) to'lov valyutasiga ({payment_currency}) mos kelishi kerak.")
        elif (amount_uzs > 0 or amount_usd > 0) and not paid_to_account:
             self.add_error('paid_to_account', "To'lov miqdori kiritilgan bo'lsa, bu maydon to'ldirilishi shart.")

        return cleaned_data 