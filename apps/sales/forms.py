from django import forms
from .models import Sale, Acquisition, Agent, FinancialAccount
from django.core.exceptions import ValidationError
from decimal import Decimal

class AcquisitionChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        currency_symbol = "UZS" if obj.transaction_currency == 'UZS' else "$"
        return f"{obj.acquisition_date.strftime('%d.%m.%y')} - {obj.ticket.description[:25]}... ({obj.available_quantity} dona) - {currency_symbol} - {obj.supplier.name[:15]}"

class SaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = [
            'sale_date', 
            'related_acquisition',
            'quantity', 
            'agent', 'client_full_name', 'client_id_number',
            'unit_sale_price', 
            'initial_payment_amount',
            'paid_to_account', 
            'notes'
        ]
        labels = {
            'sale_date': "Sotuv Sanasi va Vaqti",
            'related_acquisition': "Chipta Ombori",
            'quantity': "Miqdori",
            'agent': "Agent",
            'client_full_name': "Mijozning To'liq Ismi",
            'client_id_number': "Mijozning ID Raqami",
            'unit_sale_price': "Narxi",
            'initial_payment_amount': "Boshlang'ich To'lov Miqdori (Agent)",
            'paid_to_account': "To'lov Hisobi (Boshlang'ich / To'liq)",
            'notes': "Izohlar",
        }
        help_texts = {
            'related_acquisition': "Faqat sotuvda mavjud bo'lgan xaridlar ko'rsatiladi.",
            'unit_sale_price': "Sotuv valyutasida birlik narxni kiriting.",
            'initial_payment_amount': "Faqat agent tanlanganda ishlatiladi. Agar agent to'lov qilsa, shu yerga kiriting.",
            'paid_to_account': "Mijoz uchun to'liq to'lov yoki agent uchun boshlang'ich to'lov qabul qilingan hisob.",
        }
        widgets = {
            'sale_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control form-control-sm'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': '1'}),
            'agent': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'client_full_name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'client_id_number': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'unit_sale_price': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01'}),
            'initial_payment_amount': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01'}),
            'paid_to_account': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'notes': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        original_related_acquisition_field = self.fields['related_acquisition']
        self.fields['related_acquisition'] = AcquisitionChoiceField(
            queryset=Acquisition.objects.filter(available_quantity__gt=0)
                                      .select_related('ticket', 'supplier')
                                      .order_by('-acquisition_date', '-created_at'),
            label=original_related_acquisition_field.label,
            help_text=original_related_acquisition_field.help_text,
            required=original_related_acquisition_field.required,
            widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
        )
        
        self.fields['agent'].queryset = Agent.objects.all().order_by('name')
        self.fields['paid_to_account'].queryset = FinancialAccount.objects.filter(is_active=True).order_by('name')
        self.fields['paid_to_account'].required = False
        self.fields['initial_payment_amount'].required = False

        self.fields['client_full_name'].required = False
        self.fields['client_id_number'].required = False

    def clean(self):
        cleaned_data = super().clean()
        agent = cleaned_data.get('agent')
        client_full_name = cleaned_data.get('client_full_name')
        client_id_number = cleaned_data.get('client_id_number')
        related_acquisition = cleaned_data.get('related_acquisition')
        quantity = cleaned_data.get('quantity')
        initial_payment_amount = cleaned_data.get('initial_payment_amount')
        paid_to_account = cleaned_data.get('paid_to_account')
        unit_sale_price = cleaned_data.get('unit_sale_price')

        if agent and (client_full_name or client_id_number):
            raise ValidationError("Bir vaqtning o'zida ham agent, ham mijoz ma'lumotlarini kiritish mumkin emas.")
        
        if not agent and not (client_full_name and client_id_number):
            raise ValidationError("Agentni tanlang yoki mijozning to'liq ismi va ID raqamini kiriting.")
        
        if not agent:
            if client_full_name and not client_id_number:
                self.add_error('client_id_number', "Mijozning ID raqami kiritilishi shart.")
            if not client_full_name and client_id_number:
                self.add_error('client_full_name', "Mijozning to'liq ismi kiritilishi shart.")

        if unit_sale_price is not None and unit_sale_price <= 0:
            self.add_error('unit_sale_price', "Sotish narxi noldan katta bo'lishi kerak.")

        if related_acquisition and quantity:
            effective_available_qty = related_acquisition.available_quantity
            if self.instance and self.instance.pk and self.instance.related_acquisition_id == related_acquisition.id:
                effective_available_qty += self.instance.quantity

            if quantity > effective_available_qty:
                self.add_error('quantity', f"Kiritilgan miqdor ({quantity}) tanlangan xariddagi mavjud miqdordan ({effective_available_qty}) ortiq.")

        total_sale_amount = Decimal('0.00')
        if quantity and unit_sale_price:
            total_sale_amount = quantity * unit_sale_price

        if agent:
            if initial_payment_amount is not None:
                if initial_payment_amount < 0:
                    self.add_error('initial_payment_amount', "Boshlang'ich to'lov manfiy bo'lishi mumkin emas.")
                if initial_payment_amount > 0 and not paid_to_account:
                    self.add_error('paid_to_account', "Boshlang'ich to'lov kiritilsa, to'lov hisobi tanlanishi shart.")
                if initial_payment_amount > total_sale_amount:
                    self.add_error('initial_payment_amount', f"Boshlang'ich to'lov jami sotuv summasidan ({total_sale_amount}) oshmasligi kerak.")
            # If initial_payment_amount is None or 0, paid_to_account is not strictly needed for agent
        else:
            if initial_payment_amount is not None and initial_payment_amount > 0:
                self.add_error('initial_payment_amount', "Boshlang'ich to'lov faqat agentlar uchun kiritiladi.")
            # For client sales, if paid_to_account is not provided, it's considered unpaid/cash (depending on business rules)
            # If paid_to_account is provided, it means full payment to that account. No initial_payment field for clients.

        if related_acquisition and paid_to_account:
            sale_currency = related_acquisition.transaction_currency
            if paid_to_account.currency != sale_currency:
                self.add_error('paid_to_account', 
                               f"Tanlangan to'lov hisobining valyutasi ({paid_to_account.currency}) "
                               f"sotuv valyutasiga ({sale_currency}) mos kelmadi.")
            self.fields['paid_to_account'].queryset = FinancialAccount.objects.filter(
                is_active=True, currency=sale_currency
            ).order_by('name')
        elif paid_to_account and not related_acquisition:
             self.add_error('paid_to_account', "To'lov hisobini tekshirish uchun avval xaridni tanlang.")

        return cleaned_data 