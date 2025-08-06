"""
Management command to fix agent balances affected by incorrect return calculations.
This command recalculates agent balances using the correct return logic 
(original purchase price instead of sale price).
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from apps.contacts.models import Agent
from apps.sales.models import TicketReturn
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fix agent balances affected by incorrect return calculations'

    def add_arguments(self, parser):
        parser.add_argument(
            '--agent-id',
            type=int,
            help='Specific agent ID to fix (optional, will fix all agents if not provided)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making actual changes'
        )

    def handle(self, *args, **options):
        agent_id = options.get('agent_id')
        dry_run = options.get('dry_run', False)
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be made')
            )
        
        # Get agents to fix
        if agent_id:
            try:
                agents = [Agent.objects.get(pk=agent_id)]
                self.stdout.write(f"Fixing specific agent: {agents[0].name}")
            except Agent.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Agent with ID {agent_id} not found')
                )
                return
        else:
            # Get all agents that have returns
            from apps.sales.models import Sale
            agent_ids_with_returns = TicketReturn.objects.values_list(
                'original_sale__agent_id', flat=True
            ).distinct()
            agents = Agent.objects.filter(id__in=agent_ids_with_returns)
            self.stdout.write(f"Found {agents.count()} agents with returns to fix")
        
        total_fixed = 0
        
        for agent in agents:
            self.stdout.write(f"\n--- Processing Agent: {agent.name} (ID: {agent.pk}) ---")
            
            # Get all returns for this agent
            returns = TicketReturn.objects.filter(
                original_sale__agent=agent
            ).select_related('original_sale__related_acquisition')
            
            if not returns.exists():
                self.stdout.write("No returns found for this agent")
                continue
            
            self.stdout.write(f"Found {returns.count()} returns to process")
            
            # Calculate adjustment needed
            uzs_adjustment = 0
            usd_adjustment = 0
            
            for return_instance in returns:
                sale = return_instance.original_sale
                acquisition = sale.related_acquisition
                
                # What we incorrectly calculated (using sale amount)
                old_returned_amount = return_instance.returned_sale_amount
                old_currency = sale.sale_currency
                
                # What we should have calculated (using acquisition amount)
                new_returned_amount = return_instance.returned_acquisition_amount
                new_currency = acquisition.currency
                
                # Calculate the difference
                difference = old_returned_amount - new_returned_amount
                
                self.stdout.write(
                    f"  Return #{return_instance.pk}: "
                    f"Old: {old_returned_amount} {old_currency}, "
                    f"New: {new_returned_amount} {new_currency}, "
                    f"Difference: {difference}"
                )
                
                # Add the difference to adjustment
                # We need to add back the difference because we over-reduced the debt
                if new_currency == 'UZS':
                    uzs_adjustment += difference
                else:
                    usd_adjustment += difference
            
            # Show current and new balances
            current_uzs = agent.balance_uzs
            current_usd = agent.balance_usd
            new_uzs = current_uzs + uzs_adjustment
            new_usd = current_usd + usd_adjustment
            
            self.stdout.write(f"Current Balance: UZS {current_uzs:,.0f}, USD ${current_usd:,.2f}")
            self.stdout.write(f"Adjustment: UZS {uzs_adjustment:+,.0f}, USD ${usd_adjustment:+,.2f}")
            self.stdout.write(f"New Balance: UZS {new_uzs:,.0f}, USD ${new_usd:,.2f}")
            
            if uzs_adjustment != 0 or usd_adjustment != 0:
                if not dry_run:
                    with transaction.atomic():
                        # Apply the adjustment directly to balance fields
                        if uzs_adjustment != 0:
                            agent.add_debt(uzs_adjustment, 'UZS')
                            self.stdout.write(
                                self.style.SUCCESS(f"Applied UZS adjustment: {uzs_adjustment:+,.0f}")
                            )
                        
                        if usd_adjustment != 0:
                            agent.add_debt(usd_adjustment, 'USD')
                            self.stdout.write(
                                self.style.SUCCESS(f"Applied USD adjustment: ${usd_adjustment:+,.2f}")
                            )
                        
                        total_fixed += 1
                else:
                    self.stdout.write(
                        self.style.WARNING("Would apply adjustments (dry run mode)")
                    )
            else:
                self.stdout.write("No adjustment needed for this agent")
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"\nDRY RUN COMPLETE - {len(agents)} agents processed")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\nFIX COMPLETE - {total_fixed} agents updated")
            )
            
        self.stdout.write(
            "\nNote: This fix addresses the difference between using sale price vs. "
            "acquisition price for return calculations."
        )