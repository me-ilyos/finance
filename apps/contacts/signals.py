from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.apps import apps
import logging

from .services import AgentService
from apps.core.constants import CurrencyChoices

logger = logging.getLogger(__name__)


@receiver(post_save, sender='sales.Sale')
def handle_sale_created_or_updated(sender, instance, created, **kwargs):
    """Handle agent balance updates when sales are created or updated"""
    if instance.agent and created:
        try:
            AgentService.update_balance_on_sale(
                agent=instance.agent,
                sale_amount=instance.total_sale_amount,
                sale_currency=instance.sale_currency
            )
            logger.info(f"Updated agent {instance.agent.id} balance for new sale {instance.id}")
        except Exception as e:
            logger.error(f"Error updating agent balance for sale {instance.id}: {e}")


@receiver(post_delete, sender='sales.Sale')
def handle_sale_deleted(sender, instance, **kwargs):
    """Handle agent balance updates when sales are deleted"""
    if instance.agent:
        try:
            # Reverse the balance update by subtracting the sale amount
            if instance.sale_currency == CurrencyChoices.UZS:
                instance.agent.outstanding_balance_uzs -= instance.total_sale_amount
            elif instance.sale_currency == CurrencyChoices.USD:
                instance.agent.outstanding_balance_usd -= instance.total_sale_amount
            
            instance.agent.save(update_fields=['outstanding_balance_uzs', 'outstanding_balance_usd', 'updated_at'])
            logger.info(f"Reverted agent {instance.agent.id} balance for deleted sale {instance.id}")
        except Exception as e:
            logger.error(f"Error reverting agent balance for deleted sale {instance.id}: {e}")


@receiver(post_save, sender='accounting.FinancialAccount')
def handle_financial_account_updated(sender, instance, **kwargs):
    """Log financial account changes for audit purposes"""
    logger.info(f"Financial account {instance.id} updated: {instance.name} - Balance: {instance.current_balance}")


# Signal to ensure proper cleanup on agent deletion
@receiver(post_delete, sender='contacts.Agent')
def handle_agent_deleted(sender, instance, **kwargs):
    """Handle cleanup when agent is deleted"""
    logger.warning(f"Agent {instance.id} ({instance.name}) deleted. Check for orphaned sales and payments.") 