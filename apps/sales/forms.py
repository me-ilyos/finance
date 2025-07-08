from django import forms
from .models import Sale
from apps.inventory.models import Acquisition
from apps.contacts.models import Agent
from apps.accounting.models import FinancialAccount
from apps.core.models import Salesperson
from django.core.exceptions import ValidationError
from django.utils import timezone


class AcquisitionChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        currency_symbol = "UZS" if obj.currency == 'UZS' else "$"
        return (f"{obj.acquisition_date.strftime('%d.%m.%y')} - "
                f"{obj.ticket.description[:25]}... ({obj.available_quantity} dona) - "
                f"{currency_symbol} - {obj.supplier.name[:15]}")


class SaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = [
            'sale_date', 
            'related_acquisition',
            'quantity', 
            'agent', 'client_full_name', 'client_id_number',
            'unit_sale_price', 
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
            'paid_to_account': "To'lov Hisobi (Faqat mijoz uchun)",
            'notes': "Izohlar",
        }
        help_texts = {
            'related_acquisition': "Faqat sotuvda mavjud bo'lgan xaridlar ko'rsatiladi.",
            'unit_sale_price': "Sotuv valyutasida birlik narxni kiriting.",
            'paid_to_account': "Faqat mijoz sotib olganda to'lov hisobi talab qilinadi. Agentga sotuv qarzdorlik sifatida qayd etiladi.",
        }
        widgets = {
            'sale_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control form-control-sm'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': '1'}),
            'agent': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'client_full_name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'client_id_number': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'unit_sale_price': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01'}),
            'paid_to_account': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'notes': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)

        # Custom acquisition field with better display
        original_field = self.fields['related_acquisition']
        self.fields['related_acquisition'] = AcquisitionChoiceField(
            queryset=Acquisition.objects.filter(available_quantity__gt=0)
                                      .select_related('ticket', 'supplier')
                                      .order_by('-acquisition_date', '-created_at'),
            label=original_field.label,
            help_text=original_field.help_text,
            required=original_field.required,
            widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
        )
        
        # Set up other fields
        self.fields['agent'].queryset = Agent.objects.all().order_by('name')
        self.fields['paid_to_account'].queryset = FinancialAccount.objects.filter(is_active=True).order_by('name')
        self.fields['paid_to_account'].required = False
        self.fields['client_full_name'].required = False
        self.fields['client_id_number'].required = False
        
        # Set current datetime as default
        self.fields['sale_date'].initial = timezone.now().strftime('%Y-%m-%dT%H:%M')

    def clean(self):
        """Basic validation - business logic will be in views"""
        cleaned_data = super().clean()
        
        agent = cleaned_data.get('agent')
        client_full_name = cleaned_data.get('client_full_name')
        client_id_number = cleaned_data.get('client_id_number')
        quantity = cleaned_data.get('quantity')
        unit_sale_price = cleaned_data.get('unit_sale_price')
        related_acquisition = cleaned_data.get('related_acquisition')
        paid_to_account = cleaned_data.get('paid_to_account')

        # Basic buyer validation
        if agent and (client_full_name or client_id_number):
            raise ValidationError("Bir vaqtning o'zida ham agent, ham mijoz ma'lumotlarini kiritish mumkin emas.")
        
        if not agent and not (client_full_name and client_id_number):
            raise ValidationError("Agentni tanlang yoki mijozning to'liq ismi va ID raqamini kiriting.")

        # Basic quantity and price validation
        if quantity and quantity <= 0:
            self.add_error('quantity', "Miqdor noldan katta bo'lishi kerak.")
        
        if unit_sale_price and unit_sale_price <= 0:
            self.add_error('unit_sale_price', "Sotish narxi noldan katta bo'lishi kerak.")

        # Basic stock validation
        if related_acquisition and quantity:
            effective_available_qty = related_acquisition.available_quantity
            
            # For updates, add back the original quantity
            if self.instance.pk and self.instance.related_acquisition_id == related_acquisition.id:
                effective_available_qty += getattr(self.instance, 'quantity', 0)
            
            if quantity > effective_available_qty:
                self.add_error('quantity', f"Kiritilgan miqdor ({quantity}) mavjud miqdordan ({effective_available_qty}) ortiq.")

        # Payment validation - customers must pay immediately
        if not agent and not paid_to_account:
            self.add_error('paid_to_account', "Mijoz sotib olganda to'lov hisobi tanlanishi shart.")
        
        # Agent sales don't require payment account
        if agent and paid_to_account:
            self.add_error('paid_to_account', "Agentga sotuv qarzdorlik sifatida qayd etiladi. To'lov hisobi tanlanmasligi kerak.")

        # Currency matching validation for customer sales
        if not agent and related_acquisition and paid_to_account and paid_to_account.currency != related_acquisition.currency:
            self.add_error('paid_to_account', f"Hisob valyutasi ({paid_to_account.currency}) sotuv valyutasiga ({related_acquisition.currency}) mos kelmadi.")

        # Add salesperson for validation
        if self.current_user:
            try:
                current_salesperson = self.current_user.salesperson_profile
                cleaned_data['salesperson'] = current_salesperson
            except Salesperson.DoesNotExist:
                if not self.current_user.is_superuser:
                    raise ValidationError("Faqat sotuvchilar sotuv amalga oshira oladi.")

        return cleaned_data 