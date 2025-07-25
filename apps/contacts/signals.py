from django.db.models.signals import post_delete
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)


@receiver(post_delete, sender='sales.Sale')
def handle_sale_deleted(sender, instance, **kwargs):
    # Note: Debt handling is managed by SaleService.delete_sale() to prevent double processing
    # This signal only logs the deletion for audit purposes
    logger.info(f"Sale {instance.id} deleted. Agent debt handling managed by service layer.")
    if instance.agent:
        logger.info(f"Sale deletion involved agent {instance.agent.id} ({instance.agent.name})")
    if instance.paid_to_account:
        logger.info(f"Sale deletion involved account {instance.paid_to_account.name}")


@receiver(post_delete, sender='contacts.Agent')
def handle_agent_deleted(sender, instance, **kwargs):
    logger.warning(f"Agent {instance.id} ({instance.name}) deleted. Check for orphaned sales and payments.") 