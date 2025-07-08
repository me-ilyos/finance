from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from .models import Sale
from .forms import SaleForm
from .services import SaleService


@login_required(login_url='/core/login/')
def delete_sale(request, sale_id):
    """Delete sale - only admins with complete transaction rollback"""
    if not request.user.is_superuser:
        return JsonResponse({
            'success': False,
            'message': "Faqat administratorlar sotuvni o'chira oladi."
        })
    
    try:
        SaleService.delete_sale(sale_id, request.user)
        return JsonResponse({
            'success': True,
            'message': "Sotuv muvaffaqiyatli o'chirildi va barcha tranzaktsiyalar bekor qilindi."
        })
    except ValidationError as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })
    except Exception:
        return JsonResponse({
            'success': False,
            'message': "Sotuvni o'chirishda xatolik yuz berdi."
        })


@login_required(login_url='/core/login/')
def edit_sale(request, sale_id):
    """Edit sale - only admins with complete business logic handling"""
    if not request.user.is_superuser:
        return JsonResponse({
            'success': False,
            'message': "Faqat administratorlar sotuvni tahrirlashi mumkin."
        })
    
    try:
        sale = get_object_or_404(Sale, pk=sale_id)
        
        if request.method == 'GET':
            return _get_sale_data(sale)
        elif request.method == 'POST':
            return _update_sale_data(sale, request)
        
    except Exception:
        return JsonResponse({
            'success': False,
            'message': "Sotuvni tahrirlashda xatolik yuz berdi."
        })


def _get_sale_data(sale):
    """Return sale data for editing"""
    return JsonResponse({
        'success': True,
        'sale': {
            'id': sale.id,
            'sale_date': sale.sale_date.strftime('%Y-%m-%dT%H:%M'),
            'related_acquisition': sale.related_acquisition.id,
            'quantity': sale.quantity,
            'agent': sale.agent.id if sale.agent else None,
            'client_full_name': sale.client_full_name or '',
            'client_id_number': sale.client_id_number or '',
            'unit_sale_price': str(sale.unit_sale_price),
            'paid_to_account': sale.paid_to_account.id if sale.paid_to_account else None,
            'notes': sale.notes or '',
        }
    })


def _update_sale_data(sale, request):
    """Handle sale update"""
    form = SaleForm(request.POST, instance=sale, current_user=request.user)
    
    if form.is_valid():
        try:
            SaleService.update_sale(sale, form)
            return JsonResponse({
                'success': True,
                'message': "Sotuv muvaffaqiyatli yangilandi."
            })
        except ValidationError as e:
            return JsonResponse({
                'success': False,
                'message': f"Sotuvni yangilashda xatolik: {str(e)}"
            })
    else:
        errors = []
        for field, field_errors in form.errors.items():
            for error in field_errors:
                errors.append(f"{form.fields[field].label}: {error}")
        
        return JsonResponse({
            'success': False,
            'message': "Ma'lumotlarda xatolik mavjud:\n" + "\n".join(errors)
        }) 