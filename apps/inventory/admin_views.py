from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from .models import Acquisition
from .forms import AcquisitionForm
from .services import AcquisitionService


@login_required(login_url='/core/login/')
def delete_acquisition(request, acquisition_id):
    """Soft delete acquisition - only admins with complete transaction rollback"""
    if not request.user.is_superuser:
        return JsonResponse({
            'success': False,
            'message': "Faqat administratorlar xaridni o'chira oladi."
        })
    
    try:
        AcquisitionService.delete_acquisition(acquisition_id, request.user)
        return JsonResponse({
            'success': True,
            'message': "Xarid muvaffaqiyatli o'chirildi (nofaol qilingan)."
        })
    except ValidationError as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })
    except Exception as e:
        # Better error reporting for debugging
        import traceback
        error_details = traceback.format_exc()
        print(f"Delete acquisition error: {error_details}")  # For server logs
        return JsonResponse({
            'success': False,
            'message': f"Xaridni o'chirishda xatolik yuz berdi: {str(e)}"
        })


@login_required(login_url='/core/login/')
def edit_acquisition(request, acquisition_id):
    """Edit acquisition - only admins with complete business logic handling"""
    if not request.user.is_superuser:
        return JsonResponse({
            'success': False,
            'message': "Faqat administratorlar xaridni tahrirlashi mumkin."
        })
    
    try:
        acquisition = get_object_or_404(Acquisition, pk=acquisition_id, is_active=True)
        
        if request.method == 'GET':
            return _get_acquisition_data(acquisition)
        elif request.method == 'POST':
            return _update_acquisition_data(acquisition, request)
        
    except Exception:
        return JsonResponse({
            'success': False,
            'message': "Xaridni tahrirlashda xatolik yuz berdi."
        })


def _get_acquisition_data(acquisition):
    """Return acquisition data for editing"""
    return JsonResponse({
        'success': True,
        'acquisition': {
            'id': acquisition.id,
            'supplier': acquisition.supplier.id,
            'acquisition_date': acquisition.acquisition_date.strftime('%Y-%m-%dT%H:%M'),
            'initial_quantity': acquisition.initial_quantity,
            'unit_price': str(acquisition.unit_price),
            'currency': acquisition.currency,
            'notes': acquisition.notes or '',
            # Ticket data
            'ticket_type': acquisition.ticket.ticket_type,
            'ticket_description': acquisition.ticket.description,
            'ticket_departure_date_time': acquisition.ticket.departure_date_time.strftime('%Y-%m-%dT%H:%M'),
            'ticket_arrival_date_time': acquisition.ticket.arrival_date_time.strftime('%Y-%m-%dT%H:%M') if acquisition.ticket.arrival_date_time else '',
        }
    })


def _update_acquisition_data(acquisition, request):
    """Handle acquisition update"""
    form = AcquisitionForm(request.POST, instance=acquisition)
    
    if form.is_valid():
        try:
            AcquisitionService.update_acquisition(acquisition, form)
            return JsonResponse({
                'success': True,
                'message': "Xarid muvaffaqiyatli yangilandi."
            })
        except ValidationError as e:
            return JsonResponse({
                'success': False,
                'message': f"Xaridni yangilashda xatolik: {str(e)}"
            })
    else:
        errors = []
        for field, field_errors in form.errors.items():
            for error in field_errors:
                field_label = form.fields[field].label if field in form.fields else field
                errors.append(f"{field_label}: {error}")
        
        return JsonResponse({
            'success': False,
            'message': "Ma'lumotlarda xatolik mavjud:\n" + "\n".join(errors)
        }) 