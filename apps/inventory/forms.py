from django import forms
from .models import Acquisition, Ticket
from apps.contacts.models import Supplier
from apps.accounting.models import FinancialAccount
from django.utils import timezone

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
        # Dynamically add ticket fields to the form's fields dictionary
        # These are not part of the model form's meta fields directly
        self.fields['ticket_type'] = forms.ChoiceField(
            choices=Ticket.TicketType.choices,
            widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_ticket_type_modal'}),
            label="Chipta Turi"
        )
        self.fields['ticket_description'] = forms.CharField(
            widget=forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            label="Manzil/Tur Nomi" 
        )
        self.fields['ticket_departure_date_time'] = forms.DateTimeField(
            widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control form-control-sm'}),
            label="Uchish Vaqti",
            initial=timezone.now().strftime('%Y-%m-%dT%H:%M')
        )
        self.fields['ticket_arrival_date_time'] = forms.DateTimeField(
            required=False, 
            widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control form-control-sm'}),
            label="Qo'nish vaqti"
        )
        
        # Reorder fields to put ticket fields first, then acquisition fields
        ordered_fields = [
            'ticket_type', 'ticket_description', 'ticket_departure_date_time', 'ticket_arrival_date_time',
        ]
        # Add existing model fields (from Meta.fields) after the custom ticket fields
        for f_name in list(self.fields.keys()): # Iterate over a copy of keys
            if f_name not in ordered_fields:
                ordered_fields.append(f_name)
        
        self.order_fields(ordered_fields)

    def save(self, commit=True):
        # Create the Ticket instance first
        new_ticket = Ticket.objects.create(
            ticket_type=self.cleaned_data.get('ticket_type'),
            description=self.cleaned_data.get('ticket_description'),
            departure_date_time=self.cleaned_data.get('ticket_departure_date_time'),
            arrival_date_time=self.cleaned_data.get('ticket_arrival_date_time')
        )
        
        acquisition = super().save(commit=False)
        acquisition.ticket = new_ticket
        
        if commit:
            acquisition.save()
            # self.save_m2m() # Not needed for Acquisition model as per its definition
        return acquisition

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The model's clean method handles ensuring only one price field is set.
        # JavaScript will be used client-side for better UX.
        
        # Example: If you want to filter 'paid_from_account' based on an initial currency
        # This is more complex if currency can change dynamically on the form
        # For now, model validation handles currency mismatch on save.
        # if self.instance and self.instance.transaction_currency:
        #     self.fields['paid_from_account'].queryset = FinancialAccount.objects.filter(currency=self.instance.transaction_currency)
        # elif 'transaction_currency' in self.data: # if form is bound
        #     try:
        #         currency = self.data.get('transaction_currency')
        #         self.fields['paid_from_account'].queryset = FinancialAccount.objects.filter(currency=currency)
        #     except (ValueError, TypeError):
        #         pass # invalid currency, don't filter 