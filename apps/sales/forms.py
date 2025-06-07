from django import forms
from .models import Sale, Acquisition
from .validators import SaleValidator
from .services import SaleService
from apps.contacts.models import Agent
from apps.accounting.models import FinancialAccount
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal

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
        
        self.fields['agent'].queryset = Agent.objects.all().order_by('name')
        self.fields['paid_to_account'].queryset = FinancialAccount.objects.filter(is_active=True).order_by('name')
        self.fields['paid_to_account'].required = False
        self.fields['initial_payment_amount'].required = False
        self.fields['client_full_name'].required = False
        self.fields['client_id_number'].required = False

    def clean(self):
        """Use centralized validation"""
        cleaned_data = super().clean()
        
        try:
            # Use centralized validator
            validated_data = SaleValidator.validate_sale_data(
                sale_date=cleaned_data.get('sale_date'),
                related_acquisition=cleaned_data.get('related_acquisition'),
                quantity=cleaned_data.get('quantity'),
                agent=cleaned_data.get('agent'),
                client_full_name=cleaned_data.get('client_full_name'),
                client_id_number=cleaned_data.get('client_id_number'),
                unit_sale_price=cleaned_data.get('unit_sale_price'),
                initial_payment_amount=cleaned_data.get('initial_payment_amount'),
                paid_to_account=cleaned_data.get('paid_to_account'),
                current_sale_id=self.instance.pk if self.instance else None
            )
            
            # Update cleaned_data with validated values
            cleaned_data.update(validated_data)
            
        except ValidationError as e:
            if hasattr(e, 'error_dict'):
                for field, errors in e.error_dict.items():
                    for error in errors:
                        self.add_error(field, error.message if hasattr(error, 'message') else str(error))
            else:
                self.add_error(None, str(e))

        return cleaned_data

    def save(self, commit=True):
        """Use service to create/update sale"""
        if not commit:
            return super().save(commit=False)
        
        try:
            # Prepare sale data for service
            sale_data = {
                field: self.cleaned_data[field] 
                for field in self.Meta.fields 
                if field in self.cleaned_data
            }
            
            if self.instance.pk:
                # Update existing sale
                for field, value in sale_data.items():
                    setattr(self.instance, field, value)
                
                # Get original data for service
                original_data = {
                    'quantity': getattr(self.instance, 'quantity', 0),
                    'related_acquisition_id': getattr(self.instance, 'related_acquisition_id', None),
                    'total_sale_amount': getattr(self.instance, 'total_sale_amount', Decimal('0.00')),
                    'agent_id': getattr(self.instance, 'agent_id', None),
                    'sale_currency': getattr(self.instance, 'sale_currency', None),
                    'paid_to_account_id': getattr(self.instance, 'paid_to_account_id', None),
                }
                
                return SaleService.update_sale(self.instance, original_data)
            else:
                # Create new sale
                return SaleService.create_sale(sale_data)
                
        except Exception as e:
            self.add_error(None, f"Sotuvni saqlashda xatolik: {e}")
            return None 