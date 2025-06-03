import logging
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


def create_agent_payment(form, agent):
    """Simple function to create agent payment with error handling"""
    try:
        with transaction.atomic():
            payment = form.save(commit=False)
            payment.agent = agent
            payment.save()
            
        logger.info(f"Created payment {payment.pk} for agent {agent.pk}")
        return payment, None
        
    except ValidationError as e:
        error_msg = f"To'lovni saqlashda xatolik: {e}"
        logger.error(f"Validation error creating payment for agent {agent.pk}: {e}")
        return None, error_msg
        
    except Exception as e:
        error_msg = f"Kutilmagan xatolik: {e}"
        logger.error(f"Unexpected error creating payment for agent {agent.pk}: {e}")
        return None, error_msg


def create_agent(validated_data):
    """Create a new agent with optional initial balance"""
    from .models import Agent
    try:
        agent = Agent.objects.create(**validated_data)
        
        # Log balance information if provided
        if validated_data.get('outstanding_balance_uzs', 0) != 0 or validated_data.get('outstanding_balance_usd', 0) != 0:
            logger.info(f"Created new agent with initial balance: {agent.name} - "
                       f"UZS: {validated_data.get('outstanding_balance_uzs', 0)}, "
                       f"USD: {validated_data.get('outstanding_balance_usd', 0)}")
        else:
            logger.info(f"Created new agent: {agent.name}")
            
        return agent
    except Exception as e:
        logger.error(f"Error creating agent: {e}")
        raise


def create_supplier(validated_data):
    """Create a new supplier with optional initial balance"""
    from .models import Supplier
    try:
        supplier = Supplier.objects.create(**validated_data)
        
        # Log balance information if provided
        if validated_data.get('current_balance_uzs', 0) != 0 or validated_data.get('current_balance_usd', 0) != 0:
            logger.info(f"Created new supplier with initial balance: {supplier.name} - "
                       f"UZS: {validated_data.get('current_balance_uzs', 0)}, "
                       f"USD: {validated_data.get('current_balance_usd', 0)}")
        else:
            logger.info(f"Created new supplier: {supplier.name}")
            
        return supplier
    except Exception as e:
        logger.error(f"Error creating supplier: {e}")
        raise 