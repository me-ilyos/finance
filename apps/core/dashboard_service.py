from django.utils import timezone
from datetime import timedelta
from apps.sales.models import Sale
from apps.accounting.models import Expenditure, Transfer, Deposit
from apps.contacts.models import AgentPayment, SupplierPayment


class DashboardService:
    @staticmethod
    def get_account_transactions(account):
        """Get all transactions for a specific account"""
        transactions = []
        
        # Get client sales paid directly to this account
        client_sales = Sale.objects.filter(
            paid_to_account=account,
            agent__isnull=True
        ).select_related('related_acquisition__ticket')
        
        for sale in client_sales:
            ticket_desc = (sale.related_acquisition.ticket.get_ticket_type_display() 
                         if sale.related_acquisition and sale.related_acquisition.ticket 
                         else "Unknown Ticket")
            
            transactions.append({
                'date': sale.sale_date,
                'type': 'Sotuv (Mijoz)',
                'description': f"{ticket_desc} - {sale.client_full_name or 'N/A'}",
                'amount': sale.total_sale_amount,
                'currency': sale.sale_currency,
                'balance_effect': 'income'
            })
        
        # Get agent payments to this account
        agent_payments = AgentPayment.objects.filter(
            paid_to_account=account
        ).select_related('agent')
        
        for payment in agent_payments:
            # For cross-currency payments, show the original amount that was actually received by the account
            if payment.is_cross_currency_payment():
                display_amount = payment.original_amount
                display_currency = payment.original_currency
                is_cross_currency = True
                conversion_rate = payment.exchange_rate
                converted_amount = payment.amount
                converted_currency = payment.currency
            else:
                display_amount = payment.amount
                display_currency = payment.currency
                is_cross_currency = False
                conversion_rate = None
                converted_amount = None
                converted_currency = None
            
            transactions.append({
                'date': payment.payment_date,
                'type': 'Agent To\'lovi',
                'description': f"Agent: {payment.agent.name}",
                'amount': display_amount,
                'currency': display_currency,
                'balance_effect': 'income',
                'is_cross_currency': is_cross_currency,
                'conversion_rate': conversion_rate,
                'converted_amount': converted_amount,
                'converted_currency': converted_currency
            })
        
        # Get supplier payments from this account
        supplier_payments = SupplierPayment.objects.filter(
            paid_from_account=account
        ).select_related('supplier')
        
        for payment in supplier_payments:
            transactions.append({
                'date': payment.payment_date,
                'type': 'Ta\'minotchi To\'lovi',
                'description': f"Ta'minotchi: {payment.supplier.name}",
                'amount': payment.amount,
                'currency': payment.currency,
                'balance_effect': 'expense'
            })
        
        # Get expenditures from this account
        expenditures = Expenditure.objects.filter(paid_from_account=account)
        
        for exp in expenditures:
            transactions.append({
                'date': exp.expenditure_date,
                'type': 'Xarajat',
                'description': exp.description,
                'amount': exp.amount,
                'currency': exp.currency,
                'balance_effect': 'expense'
            })
        
        # Get transfers sent from this account
        transfers_sent = Transfer.objects.filter(from_account=account).select_related('to_account')
        
        for transfer in transfers_sent:
            description = f"Transfer to {transfer.to_account.name}"
            if transfer.is_cross_currency():
                description += f" (Rate: {transfer.conversion_rate:,.4f})"
            if transfer.description:
                description += f" - {transfer.description}"
            
            transactions.append({
                'date': transfer.transfer_date,
                'type': 'Transfer (Chiqim)',
                'description': description,
                'amount': transfer.amount,
                'currency': transfer.currency,
                'balance_effect': 'expense',
                'is_transfer': True,
                'transfer_id': transfer.id,
                'conversion_rate': transfer.conversion_rate,
                'converted_amount': transfer.converted_amount
            })
        
        # Get transfers received to this account
        transfers_received = Transfer.objects.filter(to_account=account).select_related('from_account')
        
        for transfer in transfers_received:
            description = f"Transfer from {transfer.from_account.name}"
            if transfer.is_cross_currency():
                description += f" (Rate: {transfer.conversion_rate:,.4f})"
            if transfer.description:
                description += f" - {transfer.description}"
            
            transactions.append({
                'date': transfer.transfer_date,
                'type': 'Transfer (Kirim)',
                'description': description,
                'amount': transfer.converted_amount,
                'currency': transfer.to_account.currency,
                'balance_effect': 'income',
                'is_transfer': True,
                'transfer_id': transfer.id,
                'conversion_rate': transfer.conversion_rate,
                'original_amount': transfer.amount,
                'original_currency': transfer.currency
            })
        
        transactions.sort(key=lambda t: t['date'], reverse=True)
        
        # Include deposits to this account
        deposits = Deposit.objects.filter(to_account=account)
        for dep in deposits:
            transactions.append({
                'date': dep.deposit_date,
                'type': "Kirim (Deposit)",
                'description': dep.description or 'Deposit',
                'amount': dep.amount,
                'currency': dep.currency,
                'balance_effect': 'income'
            })
        
        transactions.sort(key=lambda t: t['date'], reverse=True)
        return transactions

    @staticmethod
    def get_recent_all_transactions(limit_days=30):
        """Get recent transactions from all accounts"""
        date_limit = timezone.now() - timedelta(days=limit_days)
        transactions = []
        
        # Get recent client sales
        client_sales = Sale.objects.filter(
            sale_date__gte=date_limit,
            agent__isnull=True
        ).select_related('related_acquisition__ticket', 'paid_to_account')
        
        for sale in client_sales:
            ticket_desc = (sale.related_acquisition.ticket.get_ticket_type_display() 
                         if sale.related_acquisition and sale.related_acquisition.ticket 
                         else "Unknown Ticket")
            
            transactions.append({
                'date': sale.sale_date,
                'type': 'Sotuv (Mijoz)',
                'description': f"{ticket_desc} - {sale.client_full_name or 'N/A'}",
                'amount': sale.total_sale_amount,
                'currency': sale.sale_currency,
                'balance_effect': 'income',
                'account': sale.paid_to_account.name if sale.paid_to_account else 'N/A'
            })
        
        # Get recent agent payments
        agent_payments = AgentPayment.objects.filter(
            payment_date__gte=date_limit
        ).select_related('agent', 'paid_to_account')
        
        for payment in agent_payments:
            # For cross-currency payments, show the original amount that was actually received by the account
            if payment.is_cross_currency_payment():
                display_amount = payment.original_amount
                display_currency = payment.original_currency
                is_cross_currency = True
                conversion_rate = payment.exchange_rate
                converted_amount = payment.amount
                converted_currency = payment.currency
            else:
                display_amount = payment.amount
                display_currency = payment.currency
                is_cross_currency = False
                conversion_rate = None
                converted_amount = None
                converted_currency = None
            
            transactions.append({
                'date': payment.payment_date,
                'type': 'Agent To\'lovi',
                'description': f"Agent: {payment.agent.name}",
                'amount': display_amount,
                'currency': display_currency,
                'balance_effect': 'income',
                'account': payment.paid_to_account.name if payment.paid_to_account else 'N/A',
                'is_cross_currency': is_cross_currency,
                'conversion_rate': conversion_rate,
                'converted_amount': converted_amount,
                'converted_currency': converted_currency
            })
        
        # Get recent supplier payments
        supplier_payments = SupplierPayment.objects.filter(
            payment_date__gte=date_limit
        ).select_related('supplier', 'paid_from_account')
        
        for payment in supplier_payments:
            transactions.append({
                'date': payment.payment_date,
                'type': 'Ta\'minotchi To\'lovi',
                'description': f"Ta'minotchi: {payment.supplier.name}",
                'amount': payment.amount,
                'currency': payment.currency,
                'balance_effect': 'expense',
                'account': payment.paid_from_account.name if payment.paid_from_account else 'N/A'
            })
        
        # Get recent expenditures
        expenditures = Expenditure.objects.filter(
            expenditure_date__gte=date_limit
        ).select_related('paid_from_account')
        
        for exp in expenditures:
            transactions.append({
                'date': exp.expenditure_date,
                'type': 'Xarajat',
                'description': exp.description,
                'amount': exp.amount,
                'currency': exp.currency,
                'balance_effect': 'expense',
                'account': exp.paid_from_account.name if exp.paid_from_account else 'N/A'
            })
        
        # Get recent transfers
        recent_transfers = Transfer.objects.filter(
            transfer_date__gte=date_limit
        ).select_related('from_account', 'to_account')
        
        for transfer in recent_transfers:
            # Add sent transfer
            description = f"Transfer to {transfer.to_account.name}"
            if transfer.is_cross_currency():
                description += f" (Rate: {transfer.conversion_rate:,.4f})"
            if transfer.description:
                description += f" - {transfer.description}"
            
            transactions.append({
                'date': transfer.transfer_date,
                'type': 'Transfer (Chiqim)',
                'description': description,
                'amount': transfer.amount,
                'currency': transfer.currency,
                'balance_effect': 'expense',
                'account': transfer.from_account.name,
                'is_transfer': True,
                'transfer_id': transfer.id,
                'conversion_rate': transfer.conversion_rate,
                'converted_amount': transfer.converted_amount
            })
            
            # Add received transfer
            description = f"Transfer from {transfer.from_account.name}"
            if transfer.is_cross_currency():
                description += f" (Rate: {transfer.conversion_rate:,.4f})"
            if transfer.description:
                description += f" - {transfer.description}"
            
            transactions.append({
                'date': transfer.transfer_date,
                'type': 'Transfer (Kirim)',
                'description': description,
                'amount': transfer.converted_amount,
                'currency': transfer.to_account.currency,
                'balance_effect': 'income',
                'account': transfer.to_account.name,
                'is_transfer': True,
                'transfer_id': transfer.id,
                'conversion_rate': transfer.conversion_rate,
                'original_amount': transfer.amount,
                'original_currency': transfer.currency
            })
        
        # Include recent deposits
        recent_deposits = Deposit.objects.filter(deposit_date__gte=date_limit).select_related('to_account')
        for dep in recent_deposits:
            transactions.append({
                'date': dep.deposit_date,
                'type': "Kirim (Deposit)",
                'description': dep.description or 'Deposit',
                'amount': dep.amount,
                'currency': dep.currency,
                'balance_effect': 'income',
                'account': dep.to_account.name
            })

        transactions.sort(key=lambda t: t['date'], reverse=True)
        return transactions

    @staticmethod
    def calculate_account_statistics(accounts):
        """Calculate comprehensive account statistics"""
        if not accounts:
            return {
                'total_count': 0,
                'positive_count': 0,
                'total_uzs': 0,
                'total_usd': 0,
                'currency_count': 0,
                'negative_count': 0
            }
        
        uzs_total = 0
        usd_total = 0
        positive_count = 0
        negative_count = 0
        currencies = set()
        
        for account in accounts:
            if account.current_balance > 0:
                positive_count += 1
            elif account.current_balance < 0:
                negative_count += 1
            
            if account.currency == 'UZS':
                uzs_total += account.current_balance
            elif account.currency == 'USD':
                usd_total += account.current_balance
            
            currencies.add(account.currency)
        
        return {
            'total_count': len(accounts),
            'positive_count': positive_count,
            'negative_count': negative_count,
            'total_uzs': uzs_total,
            'total_usd': usd_total,
            'currency_count': len(currencies)
        } 