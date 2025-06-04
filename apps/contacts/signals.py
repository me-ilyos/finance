from django.db.models.signals import post_delete
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)


@receiver(post_delete, sender='sales.Sale')
def handle_sale_deleted(sender, instance, **kwargs):
    """Handle agent balance updates when sales are deleted"""
    if instance.agent:
        try:
            # Reduce the debt (reverse the sale) 
            instance.agent.reduce_debt(instance.total_sale_amount, instance.sale_currency)
            logger.info(f"Reverted agent {instance.agent.id} balance for deleted sale {instance.id}")
        except Exception as e:
            logger.error(f"Error reverting agent balance for deleted sale {instance.id}: {e}")


@receiver(post_delete, sender='contacts.Agent')
def handle_agent_deleted(sender, instance, **kwargs):
    """Handle cleanup when agent is deleted"""
    logger.warning(f"Agent {instance.id} ({instance.name}) deleted. Check for orphaned sales and payments.") 