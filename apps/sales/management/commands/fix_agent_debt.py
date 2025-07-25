from django.core.management.base import BaseCommand
from django.db.models import Sum
from apps.contacts.models import Agent
from apps.sales.models import Sale
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Check and fix agent debt inconsistencies'

    def add_arguments(self, parser):
        parser.add_argument('--fix', action='store_true', help='Actually fix the debts (dry run by default)')
        parser.add_argument('--agent-id', type=int, help='Check specific agent only')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting agent debt check...'))
        
        agents = Agent.objects.all()
        if options['agent_id']:
            agents = agents.filter(id=options['agent_id'])
        
        issues_found = 0
        
        for agent in agents:
            # Calculate expected debt from sales
            uzs_sales = agent.agent_sales.filter(sale_currency='UZS').aggregate(
                total=Sum('total_sale_amount'))['total'] or 0
            usd_sales = agent.agent_sales.filter(sale_currency='USD').aggregate(
                total=Sum('total_sale_amount'))['total'] or 0
            
            # Calculate payments made by agent
            uzs_payments = agent.payments.filter(currency='UZS').aggregate(
                total=Sum('amount'))['total'] or 0
            usd_payments = agent.payments.filter(currency='USD').aggregate(
                total=Sum('amount'))['total'] or 0
            
            # Expected debt = initial_balance + sales - payments
            expected_uzs = agent.initial_balance_uzs + uzs_sales - uzs_payments
            expected_usd = agent.initial_balance_usd + usd_sales - usd_payments
            
            # Check if current balance matches expected
            uzs_diff = agent.balance_uzs - expected_uzs
            usd_diff = agent.balance_usd - expected_usd
            
            if abs(uzs_diff) > 0.01 or abs(usd_diff) > 0.01:  # Allow small rounding differences
                issues_found += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"Agent {agent.id} ({agent.name}) has debt inconsistency:\n"
                        f"  UZS: Current={agent.balance_uzs}, Expected={expected_uzs}, Diff={uzs_diff}\n"
                        f"  USD: Current={agent.balance_usd}, Expected={expected_usd}, Diff={usd_diff}\n"
                        f"  Sales: UZS={uzs_sales}, USD={usd_sales}\n"
                        f"  Payments: UZS={uzs_payments}, USD={usd_payments}"
                    )
                )
                
                if options['fix']:
                    self.stdout.write(f"Fixing agent {agent.id} debt...")
                    agent.balance_uzs = expected_uzs
                    agent.balance_usd = expected_usd
                    agent.save(update_fields=['balance_uzs', 'balance_usd', 'updated_at'])
                    self.stdout.write(self.style.SUCCESS(f"Fixed agent {agent.id} debt"))
            else:
                self.stdout.write(f"Agent {agent.id} ({agent.name}) debt is correct")
        
        if issues_found == 0:
            self.stdout.write(self.style.SUCCESS('No debt inconsistencies found!'))
        else:
            if options['fix']:
                self.stdout.write(self.style.SUCCESS(f'Fixed {issues_found} debt inconsistencies'))
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'Found {issues_found} debt inconsistencies. Run with --fix to fix them.'
                    )
                ) 