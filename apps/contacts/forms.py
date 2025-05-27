from django import forms
from .models import Agent, Supplier

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