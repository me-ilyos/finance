from django import forms
from .models import Acquisition, Ticket
from .validators import TicketValidator, AcquisitionValidator
from .services import AcquisitionService
from apps.contacts.models import Supplier
from apps.accounting.models import FinancialAccount
from django.utils import timezone
from django.core.exceptions import ValidationError

class AcquisitionForm(forms.ModelForm):
    # Fields for creating a new Ticket
    ticket_type = forms.ChoiceField(
        choices=Ticket.TicketType.choices,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_ticket_type_modal'}),
        label="Chipta Turi"
    )
    ticket_description = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
        label="Manzil/Tur Nomi"
    )
    ticket_departure_date_time = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control form-control-sm'}),
        label="Uchish Vaqti",
        initial=timezone.now().strftime('%Y-%m-%dT%H:%M')
    )
    ticket_arrival_date_time = forms.DateTimeField(
        required=False, 
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control form-control-sm'}),
        label="Qo'nish vaqti"
    )

    # Acquisition specific fields
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
        label="Ta'minotchi"
    )
    acquisition_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
        label="Xarid Sanasi",
        initial=timezone.localdate
    )
    initial_quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
        label="Miqdori"
    )
    transaction_currency = forms.ChoiceField(
        choices=Acquisition.Currency.choices,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_transaction_currency_modal'}),
        label="Valyuta",
        initial=Acquisition.Currency.UZS
    )
    unit_price_uzs = forms.DecimalField(
        required=False, 
        max_digits=15, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01'}),
        label="Narx (UZS)"
    )
    unit_price_usd = forms.DecimalField(
        required=False, 
        max_digits=15, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01'}),
        label="Narx (USD)"
    )
    paid_from_account = forms.ModelChoiceField(
        queryset=FinancialAccount.objects.all(), 
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
        label="To'lov"
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
        label="Izohlar"
    )

    class Meta:
        model = Acquisition
        fields = [
            'supplier', 'acquisition_date', 'initial_quantity', 
            'transaction_currency', 'unit_price_uzs', 'unit_price_usd', 
            'paid_from_account', 'notes'
        ]
        exclude = ('ticket',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Reorder fields to put ticket fields first, then acquisition fields
        ordered_fields = [
            'ticket_type', 'ticket_description', 'ticket_departure_date_time', 'ticket_arrival_date_time',
            'supplier', 'acquisition_date', 'initial_quantity', 
            'transaction_currency', 'unit_price_uzs', 'unit_price_usd', 
            'paid_from_account', 'notes'
        ]
        
        self.order_fields(ordered_fields)

    def clean(self):
        """Use centralized validation"""
        cleaned_data = super().clean()
        
        # Validate ticket data
        try:
            ticket_data = TicketValidator.validate_ticket_data(
                ticket_type=cleaned_data.get('ticket_type'),
                description=cleaned_data.get('ticket_description'),
                departure_date_time=cleaned_data.get('ticket_departure_date_time'),
                arrival_date_time=cleaned_data.get('ticket_arrival_date_time')
            )
        except ValidationError as e:
            self.add_error('ticket_description', str(e))
            return cleaned_data

        # Validate acquisition data
        try:
            acquisition_data = AcquisitionValidator.validate_acquisition_data(
                supplier=cleaned_data.get('supplier'),
                acquisition_date=cleaned_data.get('acquisition_date'),
                initial_quantity=cleaned_data.get('initial_quantity'),
                transaction_currency=cleaned_data.get('transaction_currency'),
                unit_price_uzs=cleaned_data.get('unit_price_uzs'),
                unit_price_usd=cleaned_data.get('unit_price_usd'),
                paid_from_account=cleaned_data.get('paid_from_account')
            )
            
            # Update cleaned_data with validated values
            cleaned_data.update(acquisition_data)
            cleaned_data['ticket_data'] = ticket_data
            
        except ValidationError as e:
            self.add_error(None, str(e))

        return cleaned_data

    def save(self, commit=True):
        """Use service to create acquisition with ticket"""
        if not commit:
            return super().save(commit=False)
        
        try:
            # Extract ticket and acquisition data
            ticket_data = self.cleaned_data.pop('ticket_data')
            acquisition_data = {
                field: self.cleaned_data[field] 
                for field in self.Meta.fields 
                if field in self.cleaned_data
            }
            
            # Add notes if present
            if 'notes' in self.cleaned_data:
                acquisition_data['notes'] = self.cleaned_data['notes']
            
            # Use service to create acquisition
            acquisition = AcquisitionService.create_acquisition(acquisition_data, ticket_data)
            return acquisition
            
        except Exception as e:
            self.add_error(None, f"Xaridni yaratishda xatolik: {e}")
            return None