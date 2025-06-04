from django import forms
from .models import Acquisition, Ticket
from apps.contacts.models import Supplier
from apps.accounting.models import FinancialAccount
from django.utils import timezone
from django.core.exceptions import ValidationError


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
        label="Uchish Vaqti",
        initial=timezone.now().strftime('%Y-%m-%dT%H:%M')
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
        self.fields['acquisition_date'].initial = timezone.now().strftime('%Y-%m-%dT%H:%M')
        
        # Filter accounts by currency when editing
        if self.instance.pk and self.instance.currency:
            self.fields['paid_from_account'].queryset = FinancialAccount.objects.filter(
                currency=self.instance.currency, is_active=True
            )

    def clean(self):
        """Basic validation - let model handle the rest"""
        cleaned_data = super().clean()
        
        # Basic currency matching validation
        paid_from_account = cleaned_data.get('paid_from_account')
        currency = cleaned_data.get('currency')
        
        if paid_from_account and currency and paid_from_account.currency != currency:
            raise ValidationError(
                f"Payment account currency ({paid_from_account.currency}) "
                f"must match acquisition currency ({currency})"
            )
        
        return cleaned_data

    def save(self, commit=True):
        """Create ticket and acquisition"""
        if not commit:
            return super().save(commit=False)
        
        # Create ticket first
        ticket = Ticket.objects.create(
            ticket_type=self.cleaned_data['ticket_type'],
            description=self.cleaned_data['ticket_description'],
            departure_date_time=self.cleaned_data['ticket_departure_date_time'],
            arrival_date_time=self.cleaned_data.get('ticket_arrival_date_time')
        )
        
        # Create acquisition
        acquisition = super().save(commit=False)
        acquisition.ticket = ticket
        
        if commit:
            acquisition.save()
        
        return acquisition