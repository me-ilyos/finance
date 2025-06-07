from decimal import Decimal
from django.core.exceptions import ValidationError


class SaleValidator:
    """Centralized validation for sales"""

    @staticmethod
    def validate_buyer_info(agent, client_full_name, client_id_number):
        """Validate buyer information (agent or client)"""
        if agent and (client_full_name or client_id_number):
            raise ValidationError(
                "Bir vaqtning o'zida ham agent, ham mijoz ma'lumotlarini kiritish mumkin emas."
            )
        
        if not agent and not (client_full_name and client_id_number):
            raise ValidationError(
                "Agentni tanlang yoki mijozning to'liq ismi va ID raqamini kiriting."
            )
        
        if not agent:
            if client_full_name and not client_id_number:
                raise ValidationError(
                    {"client_id_number": "Mijozning ID raqami kiritilishi shart."}
                )
            if not client_full_name and client_id_number:
                raise ValidationError(
                    {"client_full_name": "Mijozning to'liq ismi kiritilishi shart."}
                )

    @staticmethod
    def validate_quantity_and_price(quantity, unit_sale_price):
        """Validate quantity and price values"""
        if not quantity or quantity <= 0:
            raise ValidationError(
                {"quantity": "Miqdor noldan katta bo'lishi kerak."}
            )
        
        if not unit_sale_price or unit_sale_price <= 0:
            raise ValidationError(
                {"unit_sale_price": "Sotish narxi noldan katta bo'lishi kerak."}
            )

    @staticmethod
    def validate_stock_availability(related_acquisition, quantity, current_sale_id=None):
        """Validate that enough stock is available for sale"""
        if not related_acquisition:
            raise ValidationError(
                {"related_acquisition": "Xarid tanlash majburiy."}
            )
        
        effective_available_qty = related_acquisition.available_quantity
        
        # For updates, add back the original quantity
        if current_sale_id:
            try:
                from .models import Sale
                original_sale = Sale.objects.get(pk=current_sale_id)
                if original_sale.related_acquisition_id == related_acquisition.id:
                    effective_available_qty += original_sale.quantity
            except Sale.DoesNotExist:
                pass
        
        if quantity > effective_available_qty:
            raise ValidationError(
                {"quantity": f"Kiritilgan miqdor ({quantity}) tanlangan xariddagi "
                            f"mavjud miqdordan ({effective_available_qty}) ortiq."}
            )

    @staticmethod
    def validate_agent_payment(agent, initial_payment_amount, total_sale_amount, paid_to_account):
        """Validate agent payment information"""
        if not agent:
            # Client sale validation
            if initial_payment_amount is not None and initial_payment_amount > 0:
                raise ValidationError(
                    {"initial_payment_amount": "Boshlang'ich to'lov faqat agentlar uchun kiritiladi."}
                )
            return
        
        # Agent sale validation
        if initial_payment_amount is not None:
            if initial_payment_amount < 0:
                raise ValidationError(
                    {"initial_payment_amount": "Boshlang'ich to'lov manfiy bo'lishi mumkin emas."}
                )
            
            if initial_payment_amount > 0 and not paid_to_account:
                raise ValidationError(
                    {"paid_to_account": "Boshlang'ich to'lov kiritilsa, to'lov hisobi tanlanishi shart."}
                )
            
            if total_sale_amount and initial_payment_amount > total_sale_amount:
                raise ValidationError(
                    {"initial_payment_amount": f"Boshlang'ich to'lov jami sotuv summasidan "
                                              f"({total_sale_amount}) oshmasligi kerak."}
                )

    @staticmethod
    def validate_payment_account_currency(related_acquisition, paid_to_account):
        """Validate that payment account currency matches sale currency"""
        if not related_acquisition or not paid_to_account:
            return
        
        sale_currency = related_acquisition.currency
        
        if paid_to_account.currency != sale_currency:
            raise ValidationError(
                {"paid_to_account": f"Tanlangan to'lov hisobining valyutasi ({paid_to_account.currency}) "
                                   f"sotuv valyutasiga ({sale_currency}) mos kelmadi."}
            )

    @staticmethod
    def validate_sale_data(sale_date, related_acquisition, quantity, agent, client_full_name, 
                          client_id_number, unit_sale_price, initial_payment_amount, 
                          paid_to_account, current_sale_id=None):
        """Main validation method for sales"""
        
        # Validate buyer information
        SaleValidator.validate_buyer_info(agent, client_full_name, client_id_number)
        
        # Validate quantity and price
        SaleValidator.validate_quantity_and_price(quantity, unit_sale_price)
        
        # Validate stock availability
        SaleValidator.validate_stock_availability(related_acquisition, quantity, current_sale_id)
        
        # Calculate total for payment validation
        total_sale_amount = None
        if quantity and unit_sale_price:
            total_sale_amount = quantity * unit_sale_price
        
        # Validate agent payment
        SaleValidator.validate_agent_payment(agent, initial_payment_amount, total_sale_amount, paid_to_account)
        
        # Validate payment account currency
        SaleValidator.validate_payment_account_currency(related_acquisition, paid_to_account)
        
        return {
            'sale_date': sale_date,
            'related_acquisition': related_acquisition,
            'quantity': quantity,
            'agent': agent,
            'client_full_name': client_full_name,
            'client_id_number': client_id_number,
            'unit_sale_price': unit_sale_price,
            'initial_payment_amount': initial_payment_amount,
            'paid_to_account': paid_to_account,
            'total_sale_amount': total_sale_amount
        }


class PaymentValidator:
    """Centralized validation for payment-related operations"""

    @staticmethod
    def validate_payment_amount(amount, currency):
        """Validate payment amount"""
        if amount is None:
            raise ValidationError("To'lov miqdori kiritilishi shart.")
        
        if amount < 0:
            raise ValidationError("To'lov miqdori manfiy bo'lishi mumkin emas.")
        
        if currency not in ['UZS', 'USD']:
            raise ValidationError(f"Noto'g'ri valyuta: {currency}")
        
        return amount

    @staticmethod
    def validate_payment_account(account, currency):
        """Validate payment account"""
        if not account:
            raise ValidationError("To'lov hisobi tanlanishi shart.")
        
        if account.currency != currency:
            raise ValidationError(
                f"Hisob valyutasi ({account.currency}) to'lov valyutasiga ({currency}) mos kelmaydi."
            )
        
        if not account.is_active:
            raise ValidationError("Faol bo'lmagan hisob tanlanadi.")
        
        return account 