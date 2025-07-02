from django import forms
from .models import Acquisition, Ticket
from django.utils import timezone


class AcquisitionForm(forms.ModelForm):
    # Ticket creation fields
    ticket_type = forms.ChoiceField(
        choices=Ticket.TicketType.choices,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
        label="Chipta Turi"
    )
    ticket_description = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
        label="Manzil/Tur Nomi"
    )
    ticket_departure_date_time = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control form-control-sm'}),
        label="Uchish Vaqti"
    )
    ticket_arrival_date_time = forms.DateTimeField(
        required=False, 
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control form-control-sm'}),
        label="Qo'nish vaqti"
    )

    class Meta:
        model = Acquisition
        fields = ['supplier', 'acquisition_date', 'initial_quantity', 'unit_price', 'currency', 'paid_from_account', 'notes']
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'acquisition_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control form-control-sm'}),
            'initial_quantity': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': '1'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01'}),
            'currency': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'paid_from_account': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'notes': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
        }
        labels = {
            'supplier': "Ta'minotchi",
            'acquisition_date': "Xarid Sanasi va Vaqti",
            'initial_quantity': "Miqdori",
            'unit_price': "Narx",
            'currency': "Valyuta",
            'paid_from_account': "To'lov Hisobi",
            'notes': "Izohlar",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set current datetime as default for both acquisition and ticket departure
        current_time = timezone.now().strftime('%Y-%m-%dT%H:%M')
        self.fields['acquisition_date'].initial = current_time
        self.fields['ticket_departure_date_time'].initial = current_time